import asyncio
import contextlib
from enum import Enum
import time
from typing import Any, Optional
from fastapi import FastAPI
import httpx
from dataclasses import dataclass, field

# Import classes
from server.entities.BaseClient import BaseClient

@dataclass
class QBitConfig:
    Url: Optional[str] = field(
        default="http://localhost:8080",
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

    class EndpointType(Enum):
        login = '/auth/login'
        version = '/app/version'
        start = '/search/start'
        status = '/search/status'
        stop = '/search/stop'
        results = '/search/results'
        add = '/torrents/add'

        def __str__(self):
            return self.value

    def GetEndpoint(self, endpoint) -> str:
        return self.UrlPath + str(endpoint)
    
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
    
    @property
    def session(self) -> httpx.AsyncClient:
        """Get the session, always using singleton and ensuring login"""
        return self._get_session()

    async def headers(self) -> dict[str, str]:
        """Get the headers for requests, ensuring login"""
        if not self._initialized:
            await self._login()
        return self._headers
    
    async def _login(self) -> None:
        """Private login function"""
        self.LOGGER.info(f"🛜 Authenticating {self.ServerName} server")
        url = self.GetEndpoint(self.EndpointType.login)
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "Referer": self.Url}
        login_session = self._get_session()
        data = {}
        if self.Config.ApiKey:
            headers["Authorization"] = f"Bearer {self.Config.ApiKey}"
        else:
            data = {"username": self.Config.Username, "password": self.Config.Password}
            resp = await login_session.post(url, data=data, headers=headers, timeout=self.TIMEOUT_DEFAULT)
            resp.raise_for_status()
        self._headers = headers
        self.LOGGER.info(f"✅ Received authentication session from {self.ServerName} server")
        self._initialized = True

    async def status(self) -> dict[str, Any] | str:
        self.LOGGER.info(f"🛜 Pinging {self.ServerName} server")
        url = self.GetEndpoint(self.EndpointType.version)
        resp = await self.session.post(url, headers=(await self.headers()), timeout=self.TIMEOUT_DEFAULT)
        resp.raise_for_status()
        version = resp.text.strip()
        self.LOGGER.info(f"✅ Received ping response from {self.ServerName} server")
        return {"version": version}
    
    async def search_start(self, pattern: str) -> int:
        self.LOGGER.info(f"🔍 Starting search query: {pattern}")
        url = self.GetEndpoint(self.EndpointType.start)
        data = {"pattern": pattern, "category": "all", "plugins": "enabled"}
        resp = await self.session.post(url, data=data, headers=(await self.headers()), timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        return int(payload.get("id"))

    async def search_status(self, job_id: int) -> dict[str, Any]:
        url = self.GetEndpoint(self.EndpointType.status)
        params = {"id": str(job_id)}
        resp = await self.session.get(url, headers=(await self.headers()), params=params, timeout=60)
        resp.raise_for_status()
        status_data = resp.json()[0]
        self.LOGGER.debug(f"🔍 Search job {job_id} reports {status_data.get('status', 'Unknown')} status with {status_data.get('total', 0)} results...")
        return status_data

    async def search_results(self, job_id: int) -> list[dict[str, Any]]:
        url = self.GetEndpoint(self.EndpointType.results)
        params = {"id": str(job_id)}
        resp = await self.session.get(url, headers=(await self.headers()), params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        self.LOGGER.info(f"📥 Received {len(payload.get('results', []))} search results from {self.ServerName} server.")
        return list(payload.get("results", []))

    async def search_stop(self, job_id: int) -> None:
        url = self.GetEndpoint(self.EndpointType.stop)
        data = {"id": str(job_id)}
        resp = await self.session.post(url, data=data, headers=(await self.headers()), timeout=self.ResponseTimeout)
        resp.raise_for_status()

    async def add_torrent(self, torrent_url: str, rename: str | None, tags: str, category: str) -> None:
        url = self.GetEndpoint(self.EndpointType.add)
        form = {"urls": torrent_url, "rename": rename or "", "tags": tags or "", "category": category}
        resp = await self.session.post(url, data=form, headers=(await self.headers()), timeout=self.ResponseTimeout)
        resp.raise_for_status()
    
    async def wait_search(self, job_id: int, limit: int, ping: int, timeout: int) -> int:
        elapsed = 0
        while True:
            status = await self.search_status(job_id)
            num_results = int(status.get("total", 0))
            if status.get("status") == "Stopped":
                return num_results
            if elapsed >= timeout or (limit and num_results >= limit):
                with contextlib.suppress(Exception):
                    await self.search_stop(job_id)
            sleep_for = min(ping, max(0, timeout - elapsed))
            if sleep_for <= 0:
                break
            await asyncio.sleep(sleep_for)
            elapsed += sleep_for
        status = await self.search_status(job_id)
        return int(status.get("total", 0))
    
    async def run_search(self, query: str, whatif: bool = False) -> list[dict[str, Any]]:
        job_id = await self.search_start(query)
        timeout = 5 if whatif else self.SearchTimeout
        search_ping = max(3, min(10, self.SearchTimeout / 2)) if self.SearchTimeout else 10
        found = await self.wait_search(job_id, limit=self.SearchLimit, ping=search_ping, timeout=timeout)
        if not found:
            return []
        return await self.search_results(job_id)