import argparse
import contextlib
import dataclasses
import json
import os
import re
import sys
import tempfile
import time
from http import cookiejar
from typing import Any
import httpx

# Import our custom implementations
from utils.customlogger import CustomLogger
from utils.filelock import FileLock
from utils.timeformatter import IsoTimeFormatter

# Global logger instance
logger = CustomLogger()


# -----------------------------
# Data structures
# -----------------------------


@dataclasses.dataclass
class ConfigQBit:
    QUrl: str
    QUsername: str
    QPassword: str
    Trackers: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ConfigLibrary:
    TypeName: str
    Url: str
    ApiKey: str
    Endpoint: str
    ProperName: str | None = None
    ProperNames: str | None = None


# -----------------------------
# Utilities
# -----------------------------


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -----------------------------
# API Clients
# -----------------------------


class QBitClient:
    Name = "qBit"
    _session = None
    _authenticated = False
    _tracker_tags = {}
    
    def __init__(self, config: ConfigQBit):
        self.config = config
        # Store tracker tags at class level for access from class methods
        QBitClient._tracker_tags = config.Trackers
    
    @classmethod
    def _get_session(cls) -> httpx.Client:
        """Get or create singleton qBittorrent session"""
        if cls._session is None:
            cls._session = httpx.Client()
        return cls._session
    
    def _login(self) -> None:
        """Private login function"""
        logger.info(f"🛜 Authenticating {self.__class__.Name} server")
        url = f"{self.config.QUrl}/api/v2/auth/login"
        data = {"username": self.config.QUsername, "password": self.config.QPassword}
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Referer": self.config.QUrl}
        session = self._get_session()
        resp = session.post(url, data=data, headers=headers, timeout=30)
        resp.raise_for_status()
        logger.info(f"✅ Received authentication session from {self.__class__.Name} server")
    
    @property
    def session(self) -> httpx.Client:
        """Get the session, always using singleton and ensuring login"""
        session = self._get_session()
        if not self._authenticated:
            self._login()
            self._authenticated = True
        return session

    def login(self) -> None:
        """Public login function that calls the private _login"""
        self._login()
    
    def reset_auth(self) -> None:
        """Reset authentication state to force re-login"""
        self._authenticated = False
    
    @classmethod
    def get_tracker_tag(cls, tracker_name: str) -> str:
        """Get the tag for a specific tracker name"""
        return cls._tracker_tags.get(tracker_name, "")

    def version(self) -> str:
        logger.info(f"🛜 Pinging {self.__class__.Name} server")
        url = f"{self.config.QUrl}/api/v2/app/version"
        resp = self.session.post(url, timeout=30)
        resp.raise_for_status()
        result = resp.text.strip()
        logger.info(f"✅ Received ping response from {self.__class__.Name} server")
        return result

    def search_start(self, pattern: str) -> int:
        logger.info(f"🔍 Starting search query: {pattern}")
        url = f"{self.config.QUrl}/api/v2/search/start"
        data = {"pattern": pattern, "category": "all", "plugins": "enabled"}
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
        resp = self.session.post(url, data=data, headers=headers, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        return int(payload.get("id"))

    def search_status(self, job_id: int) -> dict[str, Any]:
        url = f"{self.config.QUrl}/api/v2/search/status"
        params = {"id": str(job_id)}
        resp = self.session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        status_data = resp.json()[0]
        logger.debug(f"🔍 Search job {job_id} reports {status_data.get('status', 'Unknown')} status with {status_data.get('total', 0)} results...")
        return status_data

    def search_results(self, job_id: int, limit: int = 0) -> list[dict[str, Any]]:
        url = f"{self.config.QUrl}/api/v2/search/results"
        params = {"id": str(job_id), "limit": str(limit)}
        resp = self.session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        logger.info(f"📥 Received {len(payload.get('results', []))} search results from {self.__class__.Name} server.")
        return list(payload.get("results", []))

    def search_stop(self, job_id: int) -> None:
        url = f"{self.config.QUrl}/api/v2/search/stop"
        data = {"id": str(job_id)}
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
        resp = self.session.post(url, data=data, headers=headers, timeout=30)
        resp.raise_for_status()

    def add_torrent(self, torrent_url: str, rename: str | None, tags: str, category: str) -> None:
        url = f"{self.config.QUrl}/api/v2/torrents/add"
        form = {"urls": torrent_url, "rename": rename or "", "tags": tags or "", "category": category}
        resp = self.session.post(url, data=form, timeout=60)
        resp.raise_for_status()
    
    def wait_search(self, job_id: int, wait: int = 10, timeout: int = 30, whatif: bool = False) -> int:
        """Wait for search to complete and return the number of results found"""
        if whatif:
            timeout = 5
        elapsed = 0
        status = None
        while True:
            status = self.search_status(job_id)
            if status.get("status") == "Stopped":
                return int(status.get("total", 0))
            if elapsed >= timeout:
                with contextlib.suppress(Exception):
                    self.search_stop(job_id)
            sleep_for = min(wait, max(0, timeout - elapsed))
            if sleep_for <= 0:
                break
            time.sleep(sleep_for)
            elapsed += sleep_for
        status = self.search_status(job_id)
        return int(status.get("total", 0))
    
    def search(self, query: str, limit: int = 0, wait: int = 10, timeout: int = 30, whatif: bool = False) -> list[dict[str, Any]]:
        """Start a search, wait for it to complete, and return the results"""
        job_id = self.search_start(query)
        found = self.wait_search(job_id, wait=wait, timeout=timeout, whatif=whatif)
        if not found:
            return []
        return self.search_results(job_id, limit=limit)


class ArrClient:
    _session = None
    
    def __init__(self, config: ConfigLibrary):
        self.config = config
    
    @property
    def TypeName(self) -> str: return self.config.TypeName
    
    @property
    def Url(self) -> str: return self.config.Url
    
    @property
    def ApiKey(self) -> str: return self.config.ApiKey
    
    @property
    def Endpoint(self) -> str: return self.config.Endpoint
    
    @property
    def ProperName(self) -> str | None: return self.config.ProperName
    
    @property
    def ProperNames(self) -> str | None: return self.config.ProperNames
    
    @classmethod
    def _get_session(cls) -> httpx.Client:
        """Get or create singleton Arr session"""
        if cls._session is None:
            cls._session = httpx.Client()
        return cls._session
    
    @property
    def session(self) -> httpx.Client:
        """Get the session, always using singleton"""
        return self._get_session()

    def status(self) -> dict[str, Any]:
        logger.info(f"🛜 Pinging {self.config.TypeName} Arr server")
        url = f"{self.config.Url}/api/v3/system/status"
        headers = {"X-Api-Key": self.config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"✅ Received ping response from {self.config.TypeName} Arr server")
        return result

    def wanted_missing(self, page_size: int = 250) -> dict[str, Any]:
        logger.info(f"🔍 Searching for missing videos.")
        url = f"{self.config.Url}/api/v3/wanted/missing"
        headers = {"X-Api-Key": self.config.ApiKey}
        params = {"page": 1, "pageSize": page_size}
        resp = self.session.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"📺 Found {len(result.get('records', []))} missing {self.config.ProperNames.lower()}.")
        return result

    def queue(self, page_size: int = 250) -> dict[str, Any]:
        logger.info(f"🔍 Searching for queued videos.")
        url = f"{self.config.Url}/api/v3/queue"
        headers = {"X-Api-Key": self.config.ApiKey}
        params = {"page": 1, "pageSize": page_size}
        resp = self.session.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        logger.info(f"📺 Found {len(result.get('records', []))} queued {self.config.ProperNames.lower()}.")
        return result

    def lookup_video(self, external_id: str) -> dict[str, Any]:
        if self.config.TypeName == "Movies":
            external_db = "tmdb"
        elif self.config.TypeName == "TV":
            external_db = "tvdb"
        logger.info(f"🔍 Looking for {self.config.ProperName} using database {external_db}.")
        url = f"{self.config.Url}/api/v3/{self.config.Endpoint}?{external_db}Id={external_id}"
        headers = {"X-Api-Key": self.config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        logger.info(f"📺 Looked up {self.config.ProperName} from {self.config.TypeName} server: {resp.get('title')}")
        return resp.json()

    def get_video(self, item_id: str) -> dict[str, Any]:
        logger.info(f"🔍 Fetching {self.config.ProperName} from {self.config.TypeName} server.")
        url = f"{self.config.Url}/api/v3/{self.config.Endpoint}/{item_id}"
        headers = {"X-Api-Key": self.config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"📺 Fetched {self.config.ProperName} from {self.config.TypeName} server: {data.get('title')}")
        return data

    def update_rss(self) -> dict[str, Any]:
        url = f"{self.config.Url}/api/v3/command"
        headers = {"X-Api-Key": self.config.ApiKey}
        body = {
            "name": "RssSync"
        }
        logger.info(f"🌐 Sending RSS sync command to {self.config.TypeName} server.")
        resp = self.session.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()


# -----------------------------
# Core logic
# -----------------------------


def optimize_results(results: list[dict[str, Any]], type_name: str, request_obj: Any) -> list[dict[str, Any]]:
    max_seeders = max((r.get("nbSeeders", 0) for r in results), default=0) or 1
    if type_name == "Movies":
        runtime_default = 100
        weights = {"seeds_10": 7, "sizeBest": 5, "favorite": 3, "seeds_50": 2, "quality": 1}
        runtime = (request_obj or {}).get("runtime") or runtime_default
    elif type_name == "TV":
        runtime_default = 20
        weights = {"seeds_10": 7, "sizeBest": 5, "seeds_50": 3, "quality": 2, "favorite": 1}
        # TV runtime: sum of runtime of episodes in request_obj list
        if isinstance(request_obj, list):
            runtime = sum((ep.get("runtime") or runtime_default) for ep in request_obj)
        else:
            runtime = (request_obj or {}).get("runtime") or runtime_default

    # Adjust Jackett names and private tracker tags
    for r in results:
        engine = r.get("engineName")
        file_name = r.get("fileName", "")
        tags = QBitClient.get_tracker_tag(engine)
        if engine == "jackett" and "] " in file_name:
            jackett_match = re.search(r'^\[([^\]]+)\] ', file_name)
            if jackett_match:
                jackett = jackett_match.group(1)
                r["fileName"] = file_name[jackett_match.end():]
                r["jackett"] = jackett
                tags = QBitClient.get_tracker_tag(jackett)
        r["tags"] = tags
        r["lastAdded"] = IsoTimeFormatter().to_string()
        MB_per_min = float(r.get("fileSize", 0) or 1) / (1024 ** 2)
        r["fileSizeMB"] = MB_per_min
        r["seeds_10"] = r.get("nbSeeders", 0) >= (0.1 * max_seeders)
        r["seeds_50"] = r.get("nbSeeders", 0) >= (0.5 * max_seeders)
        r["quality"] = any(q in file_name for q in ("1080p", "2160p"))
        r["favorite"] = r.get("siteUrl") == "https://torrents-csv.com"
        # Size heuristics
        r["sizeMin"] = (10 * runtime) <= MB_per_min <= (60 * runtime)
        r["sizeBest"] = (25 * runtime) <= MB_per_min <= (40 * runtime)
        if type_name == "Movies":
            if MB_per_min < 25 * runtime:
                r["category"] = "SD"
            elif 25 * runtime <= MB_per_min < 60 * runtime:
                r["category"] = "HD"
            else:
                r["category"] = "UHD"
        elif type_name == "TV":
            if MB_per_min < 25 * runtime:
                r["category"] = "WEB-DL"
            elif 25 * runtime <= MB_per_min < 40 * runtime:
                r["category"] = "SD"
            elif 40 * runtime <= MB_per_min < 60 * runtime:
                r["category"] = "HD"
            else:
                r["category"] = "UHD"
        # Score
        score = 0
        for k, weight in weights.items():
            if r.get(k):
                score += weight
        r["score"] = score

    # Filter and sort
    filtered = [r for r in results if r.get("score", 0) > 5 and r.get("sizeMin")]
    filtered.sort(key=lambda r: (r.get("score", 0), r.get("pubDate") or ""), reverse=True)
    # Drop calc fields that should not persist
    for r in filtered:
        for k in ("seeds_10", "seeds_50", "quality", "favorite", "sizeMin", "sizeBest"):
            r.pop(k, None)
    return filtered


def publish_results(publish_path: str, retention_days: int, results: list[dict[str, Any]], whatif: bool = False) -> None:
    existing: list[dict[str, Any]] = []
    with contextlib.suppress(Exception):
        existing = load_json(path=publish_path)
        if not isinstance(existing, list):
            existing = []

    cutoff = IsoTimeFormatter().subtract_days(days=retention_days)

    recent: dict[str, dict[str, Any]] = {}
    for item in existing:
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
    os.makedirs(os.path.dirname(publish_path), exist_ok=True)
    save_json(path=publish_path, data=final)


# -----------------------------
# Orchestration
# -----------------------------


def init_library(name: str, config_path: str | None) -> tuple[QBitClient, ArrClient]:
    """Initialize library configuration and clients with health checks"""
    # Resolve config file default relative to this script
    if not config_path:
        script_name = os.path.splitext(os.path.basename(__file__))[0]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, f"{script_name}.json")

    logger.info(f"💡 Loading configuration file: {config_path}")
    cfg_raw = load_json(path=config_path)

    def read_library(lib_name: str) -> ConfigLibrary:
        data = cfg_raw.get(lib_name)
        if not data:
            raise RuntimeError(f"Missing config key: {lib_name}")
        defaults = {
            "TypeName": lib_name,
            "ProperName": lib_name,
            "ProperNames": f"{lib_name}(s)"
        }
        return ConfigLibrary(**{**defaults, **data})

    qbit_cfg = ConfigQBit(**cfg_raw.get(QBitClient.Name))
    lib_cfg = read_library(lib_name=name)

    qBit = QBitClient(config=qbit_cfg)
    arr = ArrClient(config=lib_cfg)
    
    logger.info(f"💡 Using {arr.TypeName} server: {arr.Url}")
    logger.info(f"💡 Using {QBitClient.Name} server: {qbit_cfg.QUrl}")

    # Health checks with retries
    def retry_until_ok(fn, label: str, pause: int, timeout: int):
        waited = 0
        while True:
            try:
                fn()
                return
            except Exception as e:
                if waited >= timeout:
                    logger.error(f"❌ Failed to connect to {label} server after {timeout}s: {e}")
                    raise
                logger.warning(f"⏳ Waiting for {label} server to start for {waited}s. Pausing for {pause}s...")
                time.sleep(pause)
                waited += pause

    retry_until_ok(fn=lambda: arr.status(), label=f"{name}", pause=15, timeout=15)
    retry_until_ok(fn=lambda: qBit.version(), label=QBitClient.Name, pause=60, timeout=60)
    
    return qBit, arr


def run_for_library(name: str, config_path: str | None, publish_path: str, retention_days: int, do_qbit: bool, whatif: bool) -> None:
    """
    Main processing function for a specific library (Movies or TV).
    
    Fetches wanted items from Arr apps, searches for torrents via qBittorrent,
    optimizes results, and publishes them to a JSON file for Torznab RSS feed.
    
    Args:
        name: Library type ("Movies" or "TV")
        config_path: Path to configuration file (optional)
        publish_path: Path to JSON file for publishing results
        retention_days: Number of days to retain records in published JSON
        do_qbit: Whether to send top result directly to qBittorrent
        whatif: Dry-run mode (simulates execution without making changes)
    """
    qBit, arr = init_library(name=name, config_path=config_path)

    # Fetch all wanted items
    wanted = arr.wanted_missing(page_size=250)
    # Fetch queued videos
    queue = arr.queue(page_size=250)
    queued = queue.get("records", [])

    # Collect all search requests
    search_requests: list[dict[str, Any]] = []

    if arr.TypeName == "Movies":
        for rec in wanted.get("records", []):
            if queued and rec.get("id") in [q.get("movieId") for q in queued if q.get("status") != "completed"]:
                logger.debug(f"🚫 Skipping queued {arr.ProperName.lower()} with status=completed: {rec.get('title')}")
                continue
            logger.info(f"🧲 Grabbing {arr.ProperName.lower()}: {rec.get('title')}")
            search_requests.append({
                "string": f"{rec.get('title')} {rec.get('year')}",
                "match": str(rec.get("year")),
                "ignore": None,
                "request": rec,
                "meta": {"type": arr.TypeName, "imdbid": rec.get("imdbId"), "genres": rec.get("genres")},
            })
    elif arr.TypeName == "TV":
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
                    logger.debug(f"🚫 Skipping queued {arr.ProperName.lower()} with status=completed: {episode_label}")
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
                        logger.info(f"🧲 Grabbing {arr.ProperName.lower()}: {label}")
                        search_requests.append({
                            "string": f"{series.get('sortTitle')} {label}",
                            "match": label,
                            "ignore": None,
                            "request": [ep],
                            "meta": {"type": arr.TypeName, "tvdbid": series.get("tvdbId"), "season": ep.get("seasonNumber"), "ep": ep.get("episodeNumber")},
                            "series": series,
                        })

    # Execute searches, optimize, optionally add top torrent
    all_top: list[dict[str, Any]] = []
    for item in search_requests:
        query = item["string"]
        match_pat = item.get("match")
        ignore_pat = item.get("ignore")
        request_obj = item.get("request")
        meta = item.get("meta", {})

        results = qBit.search(query=query, limit=0, wait=10, timeout=30, whatif=whatif)
        
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

        optimized = optimize_results(results=filtered, type_name=arr.TypeName, request_obj=request_obj)
        if optimized:
            if do_qbit and not whatif:
                top = optimized[0]
                logger.info(f"🔍 Adding torrent to {QBitClient.Name} server: {top.get('fileName')}")
                qBit.add_torrent(torrent_url=top.get("fileUrl"), rename=top.get("fileName"), tags=top.get("tags") or "", category=arr.TypeName)
                logger.info(f"✅ Received torrent response from {QBitClient.Name} server")
            elif do_qbit and whatif:
                logger.info(f"📺 Would add {arr.ProperName.lower()} torrents to {QBitClient.Name} server: {optimized[0].get('fileName')}")
            # add metadata to each optimized result
            for k, v in meta.items():
                for o in optimized:
                    o[k] = v
            all_top.extend(optimized)
            logger.info(f"🎯 Found {len(optimized)} suitable torrents on {QBitClient.Name} server for request: {query}")
        else:
            logger.error(f"😵‍💫 No suitable {arr.ProperName.lower()} torrents found for request: {query}")

    logger.info(f"📝 Writing {len(all_top)} total records to JSON file: {publish_path}")
    publish_results(publish_path=publish_path, retention_days=retention_days, results=all_top, whatif=whatif)
    arr.update_rss()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Add torrents to qBittorrent by searching wanted lists from Arr apps.")
    p.add_argument("--name", choices=["Both", "Movies", "TV"], default="Both", help="Type of content to search for: Both, Movies, or TV")
    p.add_argument("--external", type=str, default=None, help="External ID for the wanted video (TMDB/TVDB ID), suffixed with a colon and season number if applicable")
    p.add_argument("--publish", default="/app/data/torrents.json", help="Path to JSON file for publishing torrent results")
    p.add_argument("--retention", type=int, default=365, help="Number of days to retain individual records in published JSON")
    p.add_argument("--qbit", action="store_true", help="Send top result directly to qBittorrent")
    p.add_argument("--config", default=None, help="Path to JSON config. Defaults to builder.json in script directory")
    p.add_argument("--whatif", action="store_true", help="Dry-run mode. Simulates execution without making actual changes")
    p.add_argument("--noninteractive", action="store_true", help="Non-interactive mode does not print to console")
    p.add_argument("--log", action="store_true", help="Log all output for debugging. Enabling this option will significantly increase execution time.")
    return p.parse_args(argv)


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
        --name: Library type to process
            - "Both" (default): Process both Movies and TV shows
            - "Movies": Only process movies from Radarr
            - "TV": Only process TV shows from Sonarr
            
        --external: External ID for the wanted video (TMDB/TVDB ID), suffixed with a colon and comma-separated season numbers if applicable
            - When specified, only searches for this specific item instead of processing the entire wanted list
            - Uses TMDB ID for movies or TVDB ID for TV shows
            - Bypasses the normal wanted list processing workflow
            - Not implemented
            
        --publish: Path to JSON file for publishing torrent results
            - Default: Value from FEED_FILE environment variable, or "/app/data/torrents.json"
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
            
        --config: Path to JSON configuration file
            - Default: builder.json in the same directory as this script
            - Contains API keys, URLs, and settings for:
              * qBittorrent server (QUrl, QUsername, QPassword)
              * Radarr server (Movies section: Url, ApiKey, Endpoint)
              * Sonarr server (TV section: Url, ApiKey, Endpoint)
              
        --whatif: Dry-run mode
            - Simulates execution without making actual changes
            - Reduces search timeouts for testing
            - Shows what would be done without adding torrents or writing files
            
        --noninteractive: Non-interactive mode
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
        python builder.py --name TV --config /path/to/config.json --publish /path/to/output.json
    """
    args = parse_args(argv)
    
    # Update global logger with command line arguments
    global logger
    script_name = os.path.splitext(os.path.basename(__file__))[0]
    logger = CustomLogger(name=script_name, noninteractive=args.noninteractive, enable_log=args.log)
    
    lock_path = os.path.join(tempfile.gettempdir(), f"{script_name}.lock")
    lock = FileLock(lock_path)
    
    try:
        logger.info("🔒 Waiting for lock (blocking)...")
        with lock:
            logger.info("🔒 Lock acquired")
            if args.name == "Both":
                run_for_library(name="Movies", config_path=args.config, publish_path=args.publish, retention_days=args.retention, do_qbit=args.qbit, whatif=args.whatif)
                run_for_library(name="TV", config_path=args.config, publish_path=args.publish, retention_days=args.retention, do_qbit=args.qbit, whatif=args.whatif)
            else:
                run_for_library(name=args.name, config_path=args.config, publish_path=args.publish, retention_days=args.retention, do_qbit=args.qbit, whatif=args.whatif)
    except Exception as e:
        logger.error(f"❌ Script failed: {e}", exc_info=True)
        return 1
    finally:
        logger.info("🔓 Lock released")
        logger.info("👋 Exiting script...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())



