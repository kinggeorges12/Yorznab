from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from dacite import Config, from_dict
import httpx

# Import classes
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings

@dataclass
class ArrType(Enum):
    Radarr = "Radarr"
    Sonarr = "Sonarr"

@dataclass
class LibraryConfig:
    ServerType: ArrType
    Url: str
    ApiKey: str
    Endpoint: str
    TypeName: Optional[str] = None
    ServerName: Optional[str] = None
    ProperName: Optional[str] = None
    ProperNames: Optional[str] = None

@dataclass
class ArrClient:

    _session = None
    _config: LibraryConfig = None
    _config_file = "settings.yaml"

    def __init__(self, server_type: ArrType, logger: CustomLogger = None):
        self.LOGGER = CustomLogger(name=server_type.value, logger=logger)
        # Resolve config file settings.yaml
        config_raw = AppSettings(filename=ArrClient._config_file).exists(name=server_type.value).get(server_type.value)
        config_raw["ServerType"] = server_type.value
        self._config = from_dict(data_class=LibraryConfig, data=config_raw, config=Config(cast=[ArrType]))

    @dataclass
    class Mapper:
        Radarr: str
        Sonarr: str

    def serve(self, mapper: Mapper) -> str:
        match self.ServerType:
            case ArrType.Radarr:
                return mapper.Radarr
            case ArrType.Sonarr:
                return mapper.Sonarr
            case _:
                raise ValueError(f"Unknown library server: {self.ServerName}")

    def _serve(self, value: Any, mapper: Mapper) -> str:
        if value is not None: return value
        return self.serve(mapper=mapper)

    @classmethod
    def init_jellyseerr(cls, type_name: str) -> ArrClient: 
        match type_name:
            case "movie":
                return cls(ArrType.Radarr)
            case "tv":
                return cls(ArrType.Sonarr)
            case _:
                raise ValueError(f"Unknown library type: {type_name}")
    
    @property
    def ServerName(self) -> str: return self._config.ServerName if self._config.ServerName else self.ServerType.value
    
    @property
    def ServerType(self) -> ArrType: return self._config.ServerType
    
    @property
    def TypeName(self) -> str: return self.serve(self.Mapper(Radarr="Movies", Sonarr="TV"))
    
    @property
    def Url(self) -> str: return self._config.Url
    
    @property
    def Endpoint(self) -> str: return self._serve(self._config.Endpoint, self.Mapper(Radarr="movie", Sonarr="series"))
    
    @property
    def ProperName(self) -> str: return self._serve(self._config.ProperName, self.Mapper(Radarr="Movie", Sonarr="Show"))
    
    @property
    def ProperNames(self) -> str: return self._serve(self._config.ProperNames, self.Mapper(Radarr="Movies", Sonarr="Shows"))
    
    @property
    def ExternalDb(self) -> str: return self.serve(self.Mapper(Radarr="tmdb", Sonarr="tvdb"))
    
    @property
    def ExternalId(self) -> str: return self.serve(self.Mapper(Radarr="tmdbId", Sonarr="tvdbId"))

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
        self.LOGGER.info(f"🛜 Pinging {self.ServerName} Arr server")
        url = f"{self.Url}/api/v3/system/status"
        headers = {"X-Api-Key": self._config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        self.LOGGER.info(f"✅ Received ping response from {self.ServerName} Arr server")
        return result

    def wanted_missing(self, page_size: int = 250) -> dict[str, Any]:
        self.LOGGER.info(f"🔍 Searching for missing videos.")
        url = f"{self.Url}/api/v3/wanted/missing"
        headers = {"X-Api-Key": self._config.ApiKey}
        params = {"page": 1, "pageSize": page_size}
        resp = self.session.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        self.LOGGER.info(f"📺 Found {len(result.get('records', []))} missing {self.ProperNames.lower()}.")
        return result

    def queue(self, page_size: int = 250) -> dict[str, Any]:
        self.LOGGER.info(f"🔍 Searching for queued videos.")
        url = f"{self.Url}/api/v3/queue"
        headers = {"X-Api-Key": self._config.ApiKey}
        params = {"page": 1, "pageSize": page_size}
        resp = self.session.get(url, headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        self.LOGGER.info(f"📺 Found {len(result.get('records', []))} queued {self.ProperNames.lower()}.")
        return result

    # TODO: Why is this unused?
    def lookup_video(self, external_id: str) -> dict[str, Any]:
        external_db = self.ExternalDb
        self.LOGGER.info(f"🔍 Looking for {self.ProperName} using database {external_db}.")
        url = f"{self.Url}{self.Endpoint}?{external_db}Id={external_id}"
        headers = {"X-Api-Key": self._config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        self.LOGGER.info(f"📺 Looked up {self.ProperName} from {self.ServerName} server: {resp.get('title')}")
        return resp.json()

    def get_video(self, item_id: str) -> dict[str, Any]:
        self.LOGGER.info(f"🔍 Fetching {self.ProperName} from {self.ServerName} server.")
        url = f"{self.Url}{self.Endpoint}/{item_id}"
        headers = {"X-Api-Key": self._config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        self.LOGGER.info(f"📺 Fetched {self.ProperName} from {self.ServerName} server: {data.get('title')}")
        return data

    def update_rss(self) -> dict[str, Any]:
        url = f"{self.Url}/api/v3/command"
        headers = {"X-Api-Key": self._config.ApiKey}
        body = {
            "name": "RssSync"
        }
        self.LOGGER.info(f"🌐 Sending RSS sync command to {self.ServerName} server.")
        resp = self.session.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()

