# Libraries
import argparse
import os
import sys
import tempfile
import time
from typing import Any

# Import classes
from server.rss.QBitFilter import QBitFilter
from server.rss.QBitClient import QBitClient
from server.rss.ArrClient import ArrClient, ArrType

# Import utilities
from server.utils.feedfile import FeedFile
from server.utils.keystore import KeyStore
from server.utils.settings import AppSettingsUndefined
from utils.customlogger import CustomLogger
from utils.filelock import FileLock
from utils.timeformatter import IsoTimeFormatter

# Global logger instance
LOGGER = None  # Will be initialized in main() with command line arguments

# -----------------------------
# Publisher
# -----------------------------

def publish_results(publish_path: str, retention_days: int, results: list[dict[str, Any]], whatif: bool = False) -> None:
    feed_file = FeedFile(publish_path).read()

    cutoff = IsoTimeFormatter().subtract_days(days=retention_days)

    recent: dict[str, dict[str, Any]] = {}
    for item in feed_file:
        last = IsoTimeFormatter(item.get("lastAdded"))
        if last >= cutoff:
            recent[item.get("descrLink")] = item

    # Build map by descrLink
    for r in results:
        recent[r.get("descrLink")] = r

    final = list(recent.values())
    if whatif:
        print(f"Would write {len(results)} new and {len(final)} total items to {publish_path}")
        return
    FeedFile(publish_path).save(final)


# -----------------------------
# Orchestration
# -----------------------------


def init_library(server_type: ArrType) -> tuple[QBitClient, ArrClient]:
    """Initialize library configuration and clients with health checks"""
    LOGGER.info(f"💡 Loading configuration file for {QBitClient.Name} and {server_type.value}")
    qBit = QBitClient(logger=LOGGER)
    arr = ArrClient(server_type=server_type, logger=LOGGER)

    LOGGER.info(f"💡 Using {arr.ServerName} server: {arr.Url}")
    LOGGER.info(f"💡 Using {qBit.ServerName} server: {qBit.Url}")

    # Health checks with retries
    def retry_until_ok(fn, label: str, pause: int, timeout: int):
        waited = 0
        while True:
            try:
                fn()
                return
            except Exception as e:
                if waited >= timeout:
                    LOGGER.error(f"❌ Failed to connect to {label} server after {timeout}s: {e}")
                    raise
                LOGGER.warning(f"⏳ Waiting for {label} server to start for {waited}s. Pausing for {pause}s...")
                time.sleep(pause)
                waited += pause

    retry_until_ok(fn=lambda: arr.status(), label=f"{arr.ServerName}", pause=15, timeout=15)
    retry_until_ok(fn=lambda: qBit.version(), label=qBit.ServerName, pause=60, timeout=60)
    
    return qBit, arr

# -----------------------------
# Job Runner
# -----------------------------

def run_for_library(server_type: ArrType, external_id: str, publish_path: str, retention_days: int, do_qbit: bool, whatif: bool) -> None:
    """
    Main processing function for a specific library (Movies or TV).
    
    Fetches wanted items from Arr apps, searches for torrents via qBittorrent,
    optimizes results, and publishes them to a JSON file for Torznab RSS feed.
    
    Args:
        server_type: Server type ("Radarr" or "Sonarr")
        external_id: External ID for the library item (TMDB/TVDB ID) to process a specific video
        publish_path: Path to JSON file for publishing results
        retention_days: Number of days to retain records in published JSON
        do_qbit: Whether to send top result directly to qBittorrent
        whatif: Dry-run mode (simulates execution without making changes)
    """
    try:
        qBit, arr = init_library(server_type=server_type)
    except Exception as e:
        LOGGER.error(f"❌ {e}")
        return

    qFilter = QBitFilter()

    # Fetch all wanted items
    wanted = arr.wanted_missing(page_size=250)
    # Fetch queued videos
    queue = arr.queue(page_size=250)
    queued = queue.get("records", [])

    # Collect all search requests
    search_requests: list[dict[str, Any]] = []

    if arr.ServerType is ArrType.Radarr:
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
    elif arr.ServerType is ArrType.Sonarr:
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

        optimized = qFilter.optimize_results(results=filtered, server_type=arr.ServerType, request_obj=request_obj)
        if optimized:
            if do_qbit and not whatif:
                top = optimized[0]
                LOGGER.info(f"🔍 Adding torrent to {qBit.ServerName} server: {top.get('fileName')}")
                qBit.add_torrent(torrent_url=top.get("fileUrl"), rename=top.get("fileName"), tags=top.get("tags") or "", category=arr.TypeName)
                LOGGER.info(f"✅ Received torrent response from {qBit.ServerName} server")
            elif do_qbit and whatif:
                LOGGER.info(f"📺 Would add {arr.ProperName.lower()} torrents to {qBit.ServerName} server: {optimized[0].get('fileName')}")
            # add metadata to each optimized result
            for k, v in meta.items():
                for o in optimized:
                    o[k] = v
            all_top.extend(optimized)
            LOGGER.info(f"🎯 Found {len(optimized)} suitable torrents on {qBit.ServerName} server for request: {query}")
        else:
            LOGGER.warning(f"🚫 No suitable {arr.ProperName.lower()} torrents found for request: {query}")

    LOGGER.info(f"📝 Writing {len(all_top)} total records to JSON file: {publish_path}")
    publish_results(publish_path=publish_path, retention_days=retention_days, results=all_top, whatif=whatif)
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
    p.add_argument("--external", type=str, default=None, help="External ID for the wanted video (TMDB/TVDB ID), suffixed with a colon and season number if applicable")
    p.add_argument("--publish", default="/app/data/torrents.json", help="Path to JSON file for publishing torrent results")
    p.add_argument("--retention", type=int, default=365, help="Number of days to retain individual records in published JSON")
    p.add_argument("--qbit", action="store_true", help="Send top result directly to qBittorrent")
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
            
        --external: External ID for the wanted video (TMDB/TVDB ID), suffixed with a colon and comma-separated season numbers if applicable
            - When specified, only searches for this specific item instead of processing the entire wanted list
            - Uses TMDB ID for movies or TVDB ID for TV shows
            - Bypasses the normal wanted list processing workflow
            - Not implemented

        --publish: Path to JSON file for publishing torrent results
            - Default: Value from feed:file setting, or "/app/data/torrents.json"
            - Used by Torznab RSS feed generator to ingest torrent data
            - Merges new results with existing data, respecting retention policy
            
        --retention: Number of days to retain records in published JSON
            - Default: 365 days
            - Records older than this are removed from the published file
            - Based on the lastAdded timestamp field
            
        --qbit: Enable direct torrent addition to qBittorrent
            - If set, automatically adds the top-scoring torrent to qBittorrent
            - If not set, only publishes results to JSON file
            - Useful for automated downloading vs manual review
              
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
        python builder.py --name Movies --qbit
        
        # Process TV shows with custom config and publish path
        python builder.py --name TV --config /path/to/config.yaml --publish /path/to/output.yaml
    """
    args = parse_args(argv)
    
    # Update global logger with command line arguments
    global LOGGER
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    LOGGER = CustomLogger(name=script_name, silent=args.silent, enable_log=args.log)
    
    lock_path = os.path.join(tempfile.gettempdir(), f"{KeyStore.get_key('SECURE_APPID') or 'yorznab'}.lock")
    lock = FileLock(lock_path)
    
    try:
        LOGGER.info("🔒 Waiting for lock (blocking)...")
        with lock:
            LOGGER.info("🔒 Lock acquired")
            if args.server == "Both":
                run_for_library(server_type=ArrType.Radarr, external_id=args.external, publish_path=args.publish, retention_days=args.retention, do_qbit=args.qbit, whatif=args.whatif)
                run_for_library(server_type=ArrType.Sonarr, external_id=args.external, publish_path=args.publish, retention_days=args.retention, do_qbit=args.qbit, whatif=args.whatif)
            else:
                run_for_library(server_type=ArrType(args.server), external_id=args.external, publish_path=args.publish, retention_days=args.retention, do_qbit=args.qbit, whatif=args.whatif)
    except Exception as e:
        LOGGER.error(f"❌ Task runner failed: {e}", exc_info=True)
        return 1
    finally:
        LOGGER.info("🔓 Lock released")
        LOGGER.info("👋 Exiting script...")
    return 0


if __name__ == "__main__":
    sys.exit(main())



