# Libraries
import argparse
import os
import sys
import time
from typing import Any
from threading import Lock

# Import classes
from server.rss.FeedGenerator import FeedGenerator
from server.rss.QBitClient import QBitClient
from server.rss.ArrClient import ArrClient, ArrType

# Import utilities
from server.utils.feedconfig import FeedConfig
from server.utils.customlogger import CustomLogger
from server.utils.timeformatter import IsoTimeFormatter

# Global logger instance
LOGGER = None  # Will be initialized in main() with command line arguments
_lock = Lock()

# -----------------------------
# Publisher
# -----------------------------

def publish_results(feed_config: FeedConfig, retention_days: int, results: list[dict[str, Any]], whatif: bool = False) -> None:
    global LOGGER

    feed_contents = feed_config.read()

    cutoff = IsoTimeFormatter().subtract_days(days=retention_days)

    recent: dict[str, dict[str, Any]] = {}
    for item in feed_contents:
        last = IsoTimeFormatter(item.get("lastAdded"))
        if last >= cutoff:
            recent[item.get("descrLink")] = item

    # Build map by descrLink
    for r in results:
        recent[r.get("descrLink")] = r

    final = list(recent.values())
    if whatif:
        LOGGER.DEBUG(f"Would write {len(results)} new and {len(final)} total items to {feed_config.file}")
        return
    feed_config.write(final)


# -----------------------------
# Orchestration
# -----------------------------


def test_connection(name, url, fn_status, pause: int = 15, timeout: int = 15) -> bool:
    """Check client connection"""
    LOGGER.info(f"💡 Using {name} server: {url}")

    waited = 0
    while True:
        try:
            fn_status()
            return True
        except Exception as e:
            if waited >= timeout:
                LOGGER.error(f"❌ Failed to connect to {name} server after {timeout}s: {e}")
                return False
            LOGGER.warning(f"⏳ Waiting for {name} server to start for {waited}s. Pausing for {pause}s...")
            time.sleep(pause)
            waited += pause

# -----------------------------
# Job Runner
# -----------------------------

def run_for_library(server_type: ArrType, feed_config: FeedConfig, external_id: str, retention_days: int, do_download: bool, whatif: bool) -> None:
    """
    Main processing function for a specific library (Movies or TV).
    
    Fetches wanted items from Arr apps, searches for torrents via qBittorrent,
    optimizes results, and publishes them to a JSON file for Torznab RSS feed.
    
    Args:
        server_type: Server type ("Radarr" or "Sonarr")
        feed_config: Feed configuration
        external_id: External ID for the library item (TMDB/TVDB ID) to process a specific video
        retention_days: Number of days to retain records in published JSON
        do_torrent: Whether to send top result directly to qBittorrent
        whatif: Dry-run mode (simulates execution without making changes)
    """
    LOGGER.info(f"💡 Loading configuration file for {QBitClient.ServerName} and {server_type.value}")
    try:
        qBit = QBitClient()
        test_connection(name=qBit.ServerName, url=qBit.Url, fn_status=lambda: qBit.status())
    except Exception as e:
        LOGGER.error(f"❌ {e}")
        return
    try:
        arr = ArrClient(server_type=server_type)
        test_connection(name=arr.ServerName, url=arr.Url, fn_status=lambda: arr.status())
    except Exception as e:
        LOGGER.error(f"❌ {e}")
        return # TODO: run with Jellyseerr info if ArrClient fails

    LOGGER.info(f"💡 Loading configuration file for feed: {feed_config.config_path}")
    feedGenerator = FeedGenerator(feed_config=feed_config)

    # Fetch all wanted items
    wanted = arr.wanted_missing(page_size=250)
    # Fetch queued videos
    queue = arr.queue(page_size=250)
    queued = queue.get("records", [])

    # Collect all search requests
    search_requests: list[dict[str, Any]] = []

    if arr and arr.ServerType is ArrType.Radarr:
        for rec in wanted.get("records", []):
            if queued and rec.get("id") in [q.get("movieId") for q in queued if q.get("status") != "completed"]:
                LOGGER.debug(f"🚫 Skipping queued {arr.ProperName.lower()} with status=completed: {rec.get('title')}")
                continue
            LOGGER.info(f"🧲 Grabbing {arr.ProperName.lower()}: {rec.get('title')}")
            search_requests.append({
                "string": f"{rec.get('title')} {rec.get('year')}",
                "match": str(rec.get("year")),
                "ignore": None,
                "request": rec,
                "meta": {"type": arr.TypeName, "imdbid": rec.get("imdbId"), "genres": rec.get("genres")},
            })
    elif arr and arr.ServerType is ArrType.Sonarr:
        # Group by seriesId
        by_series: dict[Any, list[dict[str, Any]]] = {}
        for rec in wanted.get("records", []):
            by_series.setdefault(rec.get("seriesId"), []).append(rec)
        for series_id, episodes in by_series.items():
            series = arr.get_video(item_id=str(series_id))
            # Filter missing episodes not already queued
            episodes_missing = []
            queued_eps = {q.get("episodeId") for q in queued if q.get("status") != "completed"}
            for ep in episodes:
                if ep.get("id") not in queued_eps:
                    episodes_missing.append(ep)
                else:
                    episode_label = f"S{ep.get('seasonNumber'):02d}E{ep.get('episodeNumber'):02d}"
                    LOGGER.debug(f"🚫 Skipping queued {arr.ProperName.lower()} with status=completed: {episode_label}")
            if not episodes_missing:
                continue
            # Group by season
            by_season: dict[int, list[dict[str, Any]]] = {}
            for ep in episodes_missing:
                by_season.setdefault(ep.get("seasonNumber"), []).append(ep)
            for season_num, eps in by_season.items():
                season_info = next((s for s in series.get("seasons", []) if s.get("seasonNumber") == season_num), None)
                total_eps = (season_info or {}).get("statistics", {}).get("totalEpisodeCount") or 0
                if total_eps and total_eps == len(eps):
                    season_label = f"S{season_num:02d}"
                    search_requests.append({
                        "string": f"{series.get('sortTitle')} {season_label}",
                        "match": f"({season_label}|Season 0?{season_num})",
                        "ignore": r"E\d{2,3}\D",
                        "request": eps,
                        "meta": {"type": arr.TypeName, "tvdbid": series.get("tvdbId"), "season": season_num, "ep": 0},
                        "series": series,
                    })
                else:
                    for ep in eps:
                        label = f"S{ep.get('seasonNumber'):02d}E{ep.get('episodeNumber'):02d}"
                        LOGGER.info(f"🧲 Grabbing {arr.ProperName.lower()}: {label}")
                        search_requests.append({
                            "string": f"{series.get('sortTitle')} {label}",
                            "match": label,
                            "ignore": None,
                            "request": [ep],
                            "meta": {"type": arr.TypeName, "tvdbid": series.get("tvdbId"), "season": ep.get("seasonNumber"), "ep": ep.get("episodeNumber")},
                            "series": series,
                        })

    # Filter by external ID if initiated from webhook
    if external_id:
        if arr.ServerType is ArrType.Radarr:
            search_requests = [item for item in search_requests if item.get("meta", {}).get("imdbId") == external_id]
        if arr.ServerType is ArrType.Sonarr:
            search_requests = [item for item in search_requests if item.get("meta", {}).get("tvdbId") == external_id]
    
    # Execute searches, optimize, optionally add top torrent
    all_top: list[dict[str, Any]] = []
    for item in search_requests:
        query = item["string"]
        match_pat = item.get("match")
        ignore_pat = item.get("ignore")
        request_obj = item.get("request")
        meta = item.get("meta", {})

        results = qBit.run_search(query=query, whatif=whatif)
        
        # Filter
        filtered: list[dict[str, Any]] = []
        for r in results:
            name_str = r.get("fileName") or ""
            matched = (match_pat is None) or (match_pat and (match_pat in name_str or __import__("re").search(match_pat, name_str)))
            ignored = False
            if ignore_pat:
                ignored = bool(__import__("re").search(ignore_pat, name_str))
            errored = (r.get("fileSize") == -1)
            if matched and (not ignored) and (not errored):
                filtered.append(r)

        optimized = feedGenerator.optimize_results(results=filtered, server_type=arr.ServerType, request_obj=request_obj)
        if optimized:
            # Download top result to qBittorrent
            if do_download and not whatif:
                top = optimized[0]
                LOGGER.info(f"🔍 Adding torrent to {qBit.ServerName} server: {top.get('fileName')}")
                qBit.add_torrent(torrent_url=top.get("fileUrl"), rename=top.get("fileName"), tags=top.get("tags") or "", category=arr.TypeName)
                LOGGER.info(f"✅ Received torrent response from {qBit.ServerName} server")
            elif do_download and whatif:
                LOGGER.info(f"📺 Would add {arr.ProperName.lower()} torrents to {qBit.ServerName} server: {optimized[0].get('fileName')}")
            # add metadata to each optimized result
            for k, v in meta.items():
                for o in optimized:
                    o[k] = v
            all_top.extend(optimized)
            LOGGER.info(f"🎯 Found {len(optimized)} suitable torrents on {qBit.ServerName} server for request: {query}")
        else:
            LOGGER.warning(f"🚫 No suitable {arr.ProperName.lower()} torrents found for request: {query}")

    LOGGER.info(f"📝 Writing {len(all_top)} total records to JSON file: {feedGenerator.PublishPath}")
    publish_results(feed_config=feed_config, retention_days=retention_days, results=all_top, whatif=whatif)
    arr.update_rss()

# -----------------------------
# Parser
# -----------------------------

def case_insensitive_choice(choices: list[str]):
    lookup = {c.lower(): c for c in choices}
    fallback = choices[0]

    def convert(value: str):
        return lookup.get(value.lower(), fallback)

    return convert

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Add torrents to qBittorrent by searching wanted lists from Arr apps.")
    p.add_argument("--server", choices=["Both", "Radarr", "Sonarr"], type=case_insensitive_choice(["Both", "Radarr", "Sonarr"]), default="Both", help="Server to process: Both, Radarr, or Sonarr")
    p.add_argument("--feed", action='append', type=str, default=None, help="Name of the feed for generating RSS feed (default=myfeed).")
    p.add_argument("--external", type=str, default=None, help="External ID for the wanted video (TMDB/TVDB ID), suffixed with a colon and season number if applicable")
    p.add_argument("--retention", type=int, default=365, help="Number of days to retain individual records in published JSON")
    p.add_argument("--download", action="store_true", help="Send top result directly to qBittorrent")
    p.add_argument("--whatif", action="store_true", help="Dry-run mode. Simulates execution without making actual changes")
    p.add_argument("--silent", action="store_true", help="Silent mode does not print to console")
    p.add_argument("--log", action="store_true", help="Log all output for debugging. Enabling this option will significantly increase execution time.")
    return p.parse_args(argv)

# -----------------------------
# Entrypoint
# -----------------------------

def main(argv: list[str] | None = None) -> int:
    """
    Main entry point for the library requests script.
    
    This script searches for missing movies/TV shows from Radarr/Sonarr (Arr apps),
    finds torrents via qBittorrent's search plugins (including Jackett integration),
    optimizes results based on seeders, file size, and quality preferences,
    and optionally adds the best torrents directly to qBittorrent for download.
    
    Args:
        argv: Optional command line arguments. If None, uses sys.argv.
        
    Command Line Arguments:
        --server: Server to process
            - "Both" (default): Process both Movies and TV shows
            - "Radarr": Only process movies from Radarr
            - "Sonarr": Only process TV shows from Sonarr

        --feed: YAML files in the configuration directory containing feed settings
            - Path to the YAML file that defines the RSS feed structure and content
            - Default: Run all feeds in the configuration directory if not specified
            - Usage: --feed private_trackers --feed public_trackers --feed feed3

        --external: External ID for the wanted video (TMDB/TVDB ID), suffixed with a colon and comma-separated season numbers if applicable
            - When specified, only searches for this specific item instead of processing the entire wanted list
            - Uses TMDB ID for movies or TVDB ID for TV shows
            - Bypasses the normal wanted list processing workflow
            - Not implemented

        --retention: Number of days to retain records in published JSON
            - Default: 365 days
            - Records older than this are removed from the published file
            - Based on the lastAdded timestamp field
            
        --download: Send top result directly to qBittorrent
            - If set, automatically adds the top-scoring torrent to qBittorrent
            - Useful for automated downloading vs using Radarr/Sonarr to manage downloads
              
        --whatif: Dry-run mode
            - Simulates execution without making actual changes
            - Reduces search timeouts for testing
            - Shows what would be done without adding torrents or writing files
            
        --silent: Silent mode
            - Suppresses console output to avoid conflicts with return statements in nested scripts
            - Useful when calling this script from other automation tools
            
        --log: Enable detailed logging
            - Logs all output to a temporary file for debugging
            - Significantly increases execution time due to file I/O
            - Log file location is printed when logging is enabled
            
    Returns:
        int: Exit code (0 for success)
        
    Example Usage:
        # Test run for both libraries without making changes
        python builder.py --whatif
        
        # Process only movies and add torrents to qBittorrent
        python builder.py --name Movies --torrent
        
        # Process TV shows with custom config and publish path
        python builder.py --name TV --config /path/to/config.yaml --publish /path/to/output.yaml
    """
    # Update global logger with command line arguments
    global LOGGER
    
    args = parse_args(argv)
    
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    LOGGER = CustomLogger(name=script_name, silent=args.silent, enable_log=args.log)
    
    for feed_name in args.feed:
        try:
            LOGGER.info("🔏 Waiting for builder lock...")
            with _lock:
                LOGGER.info("🔒 Acquired builder lock")
                feed_config = FeedConfig(feed_name)
                if args.server == "Both":
                    run_for_library(server_type=ArrType.Radarr, feed_config=feed_config, external_id=args.external, retention_days=args.retention, do_download=args.download, whatif=args.whatif)
                    run_for_library(server_type=ArrType.Sonarr, feed_config=feed_config, external_id=args.external, retention_days=args.retention, do_download=args.download, whatif=args.whatif)
                else:
                    run_for_library(server_type=ArrType(args.server), feed_config=feed_config, external_id=args.external, retention_days=args.retention, do_download=args.download, whatif=args.whatif)
        except Exception as e:
            LOGGER.error(f"❌ Task runner failed: {e}", exc_info=True)
        finally:
            LOGGER.info("🔓 Lock released")
            LOGGER.info("👋 Finishing RSS build...")
    return 0


if __name__ == "__main__":
    sys.exit(main())



