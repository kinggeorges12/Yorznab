import contextlib
import os
import time
from typing import Any, Optional
from dacite import from_dict
from dacite.exceptions import MissingValueError
import httpx
from dataclasses import dataclass

# Import classes
from server import PROJECT_ROOT
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings, AppSettingsUndefined

@dataclass
class QBitConfig:
    ServerType: str
    Url: str
    URLFrom: str
    ApiKey: Optional[str] = None
    Username: Optional[str] = None
    Password: Optional[str] = None
    SearchTimeout: Optional[int] = 60
    SearchLimit: Optional[int] = 0
    SearchPing: Optional[int] = 10
    ServerName: Optional[str] = None

@dataclass
class QBitClient:
    Name: str = "qBittorrent"
    _config: QBitConfig = None
    _config_file = "settings.yaml"
    _session: httpx.Client | None = None
    _headers: dict[str, str] = None
    _authenticated: bool = False
    _response_timeout: int = 60
    
    def __init__(self):
        self.LOGGER = CustomLogger(name=self.Name)
        # Resolve config file settings.yaml
        try:
            config_raw = AppSettings(filename=self._config_file).exists(name=self.Name).get(key=self.Name, exists=True)
        except AppSettingsUndefined as e:
            self.LOGGER.error(f"☠️ Critical error: unable to continue without {self.Name}.")
            raise Exception(e)
        config_raw["ServerType"] = self.Name # Required field
        try:
            self._config = from_dict(data_class=QBitConfig, data=config_raw)
        except MissingValueError as e: # dacite.exceptions.MissingValueError: missing value for field "Url"
            self.LOGGER.error(f"☠️ Trouble parsing field for {self.Name}, check file: {os.path.join(PROJECT_ROOT, self._config_file)}")
            raise Exception(e)

    @property
    def ServerName(self) -> str: return self.ServerType
    
    @property
    def ServerType(self) -> str: return self._config.ServerType
    
    @property
    def ApiVersion(self) -> str: return '/api/v2'
    
    @property
    def Url(self) -> str: return self._config.Url + self.ApiVersion
    
    @property
    def Filters(self) -> bool | None: return self._config.Filters
    
    @property
    def SearchTimeout(self) -> int | None: return self._config.SearchTimeout if self._config.SearchTimeout else 60
    
    @property
    def SearchLimit(self) -> int | None: return self._config.SearchLimit if self._config.SearchLimit else 0
    
    @property
    def SearchPing(self) -> int | None: return self._config.SearchPing if self._config.SearchPing else 10
    
    @classmethod
    def _get_session(cls) -> httpx.Client:
        """Get or create singleton qBittorrent session"""
        if cls._session is None:
            cls._session = httpx.Client()
        return cls._session
    
    @classmethod
    def _set_session_header(cls, headers: dict) -> httpx.Client:
        """Get or create singleton qBittorrent session"""
        cls._headers = headers
        return cls._session
    
    def _login(self) -> None:
        """Private login function"""
        self.LOGGER.info(f"🛜 Authenticating {self.ServerName} server")
        url = f"{self.Url}/auth/login"
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Referer": self.Url}
        session = self._get_session()
        data = {}
        if self._config.ApiKey:
            headers["Authorization"] = f"Bearer {self._config.ApiKey}"
        else:
            data = {"username": self._config.Username, "password": self._config.Password}
            resp = session.post(url, data=data, headers=headers, timeout=30)
            resp.raise_for_status()
        self._set_session_header(headers)
        self.LOGGER.info(f"✅ Received authentication session from {self.ServerName} server")
    
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

    def status(self) -> str:
        self.LOGGER.info(f"🛜 Pinging {self.ServerName} server")
        url = f"{self.Url}/app/version"
        resp = self.session.post(url, headers=self._headers, timeout=30)
        resp.raise_for_status()
        result = resp.text.strip()
        self.LOGGER.info(f"✅ Received ping response from {self.ServerName} server")
        return result

    def search_start(self, pattern: str) -> int:
        self.LOGGER.info(f"🔍 Starting search query: {pattern}")
        url = f"{self.Url}/search/start"
        data = {"pattern": pattern, "category": "all", "plugins": "enabled"}
        resp = self.session.post(url, data=data, headers=self._headers, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        return int(payload.get("id"))

    def search_status(self, job_id: int) -> dict[str, Any]:
        url = f"{self.Url}/search/status"
        params = {"id": str(job_id)}
        resp = self.session.get(url, headers=self._headers, params=params, timeout=60)
        resp.raise_for_status()
        status_data = resp.json()[0]
        self.LOGGER.debug(f"🔍 Search job {job_id} reports {status_data.get('status', 'Unknown')} status with {status_data.get('total', 0)} results...")
        return status_data

    def search_results(self, job_id: int) -> list[dict[str, Any]]:
        url = f"{self.Url}/search/results"
        params = {"id": str(job_id)} # Optional limit parameter
        resp = self.session.get(url, headers=self._headers, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        self.LOGGER.info(f"📥 Received {len(payload.get('results', []))} search results from {self.ServerName} server.")
        return list(payload.get("results", []))

    def search_stop(self, job_id: int) -> None:
        url = f"{self.Url}/search/stop"
        data = {"id": str(job_id)}
        resp = self.session.post(url, data=data, headers=self._headers, timeout=self._response_timeout)
        resp.raise_for_status()

    def add_torrent(self, torrent_url: str, rename: str | None, tags: str, category: str) -> None:
        url = f"{self.Url}/torrents/add"
        form = {"urls": torrent_url, "rename": rename or "", "tags": tags or "", "category": category}
        resp = self.session.post(url, data=form, headers=self._headers, timeout=self._response_timeout)
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
        found = self.wait_search(job_id, limit=self.SearchLimit, ping=self.SearchPing, timeout=timeout)
        if not found:
            return []
        return self.search_results(job_id)
