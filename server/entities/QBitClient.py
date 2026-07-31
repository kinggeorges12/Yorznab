import contextlib
import time
from typing import Any, Optional
import httpx
from dataclasses import dataclass, field

# Import classes
from server.entities.BaseClient import BaseClient

@dataclass
class QBitConfig:
    Url: Optional[str] = field(
        default=None,
        metadata={
            "name": "qBittorrent Server",
            "description": "URL used to connect to the qBittorrent server, including http(s)://, port, and urlbase if required"
        }
    )
    ApiKey: Optional[str] = field(
        default=None,
        metadata={
            "name": "API Key",
            "password": True,
            "description": "Find API key in new versions of qBittorrent > Tools > Options > WebUI"
        }
    )
    Username: Optional[str] = field(
        default=None,
        metadata={
            "name": "Username",
            "description": "Find Username in qBittorrent > Tools > Options > WebUI"
        }
    )
    Password: Optional[str] = field(
        default=None,
        metadata={
            "name": "Password",
            "password": True,
            "description": "Leave the ApiKey blank if using username/password authentication"
        }
    )
    SearchTimeout: Optional[int] = field(
        default=60,
        metadata={
            "name": "Search Timeout",
            "description": "Time to wait for search to complete (in seconds)",
            "min": 1,
            "max": 3600
        }
    )
    SearchLimit: Optional[int] = field(
        default=0,
        metadata={
            "name": "Search Limit",
            "description": "Maximum number of results to wait for before returning, or 0 for unlimited",
            "min": 0
        }
    )

@dataclass
class QBitClient(BaseClient[QBitConfig]):
    
    def __init__(self):
        # Initialize _name and _config_file
        self._server_type = "qBittorrent"
        super().__init__(name=self.ServerType)
    
    @property
    def DefaultUrl(self) -> str: return "http://localhost:8080"
    
    @property
    def ServerType(self) -> str: return self._server_type
    
    @property
    def ApiVersion(self) -> str: return '/api/v2'
    
    @property
    def Filters(self) -> bool | None: return self.Config.Filters
    
    @property
    def SearchTimeout(self) -> int | None: return self.Config.SearchTimeout if self.Config.SearchTimeout else 60
    
    @property
    def SearchLimit(self) -> int | None: return self.Config.SearchLimit if self.Config.SearchLimit else 0
    
    @property
    def SearchPing(self) -> int | None: return self.Config.SearchPing if self.Config.SearchPing else 10
    
    @property
    def ResponseTimeout(self) -> int | None: return 60
    
    def _set_session_header(self, headers: dict) -> httpx.Client:
        """Get or create singleton qBittorrent session"""
        self._headers = headers
        return self._session
    
    def _login(self) -> None:
        """Private login function"""
        self.LOGGER.info(f"🛜 Authenticating {self.ServerName} server")
        url = f"{self.UrlPath}/auth/login"
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Referer": self.Url}
        session = self._get_session()
        data = {}
        if self.Config.ApiKey:
            headers["Authorization"] = f"Bearer {self.Config.ApiKey}"
        else:
            data = {"username": self.Config.Username, "password": self.Config.Password}
            resp = session.post(url, data=data, headers=headers, timeout=self.TIMEOUT_DEFAULT)
            resp.raise_for_status()
        self._set_session_header(headers)
        self.LOGGER.info(f"✅ Received authentication session from {self.ServerName} server")
    
    @property
    def session(self) -> httpx.Client:
        """Get the session, always using singleton and ensuring login"""
        session = self._get_session()
        if not self._initialized:
            self._login()
            self._initialized = True
        return session

    def login(self) -> None:
        """Public login function that calls the private _login"""
        self._login()

    def status(self) -> dict[str, Any] | str:
        self.LOGGER.info(f"🛜 Pinging {self.ServerName} server")
        url = f"{self.UrlPath}/app/version"
        resp = self.session.post(url, headers=self._headers, timeout=self.TIMEOUT_DEFAULT)
        resp.raise_for_status()
        version = resp.text.strip()
        self.LOGGER.info(f"✅ Received ping response from {self.ServerName} server")
        return {"version": version}

    def search_start(self, pattern: str) -> int:
        self.LOGGER.info(f"🔍 Starting search query: {pattern}")
        url = f"{self.UrlPath}/search/start"
        data = {"pattern": pattern, "category": "all", "plugins": "enabled"}
        resp = self.session.post(url, data=data, headers=self._headers, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        return int(payload.get("id"))

    def search_status(self, job_id: int) -> dict[str, Any]:
        url = f"{self.UrlPath}/search/status"
        params = {"id": str(job_id)}
        resp = self.session.get(url, headers=self._headers, params=params, timeout=60)
        resp.raise_for_status()
        status_data = resp.json()[0]
        self.LOGGER.debug(f"🔍 Search job {job_id} reports {status_data.get('status', 'Unknown')} status with {status_data.get('total', 0)} results...")
        return status_data

    def search_results(self, job_id: int) -> list[dict[str, Any]]:
        url = f"{self.UrlPath}/search/results"
        params = {"id": str(job_id)} # Optional limit parameter
        resp = self.session.get(url, headers=self._headers, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        self.LOGGER.info(f"📥 Received {len(payload.get('results', []))} search results from {self.ServerName} server.")
        return list(payload.get("results", []))

    def search_stop(self, job_id: int) -> None:
        url = f"{self.UrlPath}/search/stop"
        data = {"id": str(job_id)}
        resp = self.session.post(url, data=data, headers=self._headers, timeout=self.ResponseTimeout)
        resp.raise_for_status()

    def add_torrent(self, torrent_url: str, rename: str | None, tags: str, category: str) -> None:
        url = f"{self.UrlPath}/torrents/add"
        form = {"urls": torrent_url, "rename": rename or "", "tags": tags or "", "category": category}
        resp = self.session.post(url, data=form, headers=self._headers, timeout=self.ResponseTimeout)
        resp.raise_for_status()
    
    def wait_search(self, job_id: int, limit: int, ping: int, timeout: int) -> int:
        """Wait for search to complete and return the number of results found"""
        elapsed = 0
        status = None
        while True:
            status = self.search_status(job_id)
            num_results = int(status.get("total", 0))
            if status.get("status") == "Stopped":
                return num_results
            if elapsed >= timeout or (limit and num_results >= limit):
                with contextlib.suppress(Exception):
                    self.search_stop(job_id)
            sleep_for = min(ping, max(0, timeout - elapsed))
            if sleep_for <= 0:
                break
            time.sleep(sleep_for)
            elapsed += sleep_for
        status = self.search_status(job_id)
        return int(status.get("total", 0))
    
    def run_search(self, query: str, whatif: bool = False) -> list[dict[str, Any]]:
        """Start a search, wait for it to complete, and return the results"""
        job_id = self.search_start(query)
        # Set lower timeout for whatif mode
        timeout = 5 if whatif else self.SearchTimeout
        search_ping = max(3, min(10, self.SearchTimeout / 2)) if self.SearchTimeout else 10
        found = self.wait_search(job_id, limit=self.SearchLimit, ping=search_ping, timeout=timeout)
        if not found:
            return []
        return self.search_results(job_id)
