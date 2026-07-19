from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Any, Optional
from dacite import Config, from_dict
from dacite.exceptions import MissingValueError
from fastapi import requests
import httpx

# Import classes
from server import PROJECT_ROOT
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.utils.keystore import KeyStore
from server.utils.settings import AppSettings, AppSettingsUndefined

class ArrType(Enum):
    Radarr = "Radarr"
    Sonarr = "Sonarr"

@dataclass
class LibraryConfig:
    ServerType: ArrType
    Url: str
    ApiKey: str
    URLBase: Optional[str] = None
    TypeName: Optional[str] = None
    ServerName: Optional[str] = None
    ProperName: Optional[str] = None
    ProperNames: Optional[str] = None

@dataclass
class ArrClient:

    _session = None
    _config: LibraryConfig = None
    _config_file = "settings.yaml"

    def __init__(self, server_type: ArrType):
        self.LOGGER = CustomLogger(name=server_type.value)
        # Resolve config file settings.yaml
        try:
            config_raw = AppSettings(filename=ArrClient._config_file).exists(name=server_type.value).get(key=server_type.value, exists=True)
        except AppSettingsUndefined as e:
            self.LOGGER.warning(f"🚩 Server has bad configuration for {server_type.value}. Continuing without this app.")
            raise Exception(e)
        config_raw["ServerType"] = server_type.value
        try:
            self._config = from_dict(data_class=LibraryConfig, data=config_raw, config=Config(cast=[ArrType]))
        except MissingValueError as e:
            self.LOGGER.error(f"🚩 Trouble parsing field for {server_type.value}, check file: {os.path.join(PROJECT_ROOT, self._config_file)}")
            raise Exception(e)

    class EndpointType(Enum):
        api = ''
        command = '/command'
        indexer = '/indexer'
        queue = '/queue'
        status = '/system/status'
        wanted = '/wanted/missing'
        def __str__(self):
                return self.value

    @dataclass
    class Mapper:
        Radarr: str
        Sonarr: str

    def serve(self, mapper: Mapper, value: Any = None) -> str:
        if value is not None: return value
        match self.ServerType:
            case ArrType.Radarr:
                return mapper.Radarr
            case ArrType.Sonarr:
                return mapper.Sonarr
            case _:
                raise ValueError(f"Unknown library server: {self.ServerName}")

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
    def URLBase(self) -> str: return self.serve(self.Mapper(Radarr="", Sonarr=""), self._config.URLBase)
    
    @property
    def APIVersion(self) -> str: return '/api/v3'

    def GetEndpoint(self, endpoint: ArrClient.EndpointType) -> str:
        url_path = self.Url + self.URLBase + self.APIVersion
        if endpoint == self.__class__.EndpointType.api:
            return url_path + self.serve(self.Mapper(Radarr="/movie", Sonarr="/series"))
        else:
            return url_path + str(endpoint)
    
    @property
    def ProperName(self) -> str: return self.serve(self.Mapper(Radarr="Movie", Sonarr="Show"), self._config.ProperName)
    
    @property
    def ProperNames(self) -> str: return self.serve(self.Mapper(Radarr="Movies", Sonarr="Shows"), self._config.ProperNames)
    
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
        headers = {"X-Api-Key": self._config.ApiKey}
        resp = self.session.get(self.GetEndpoint(self.EndpointType.status), headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        self.LOGGER.info(f"✅ Received ping response from {self.ServerName} Arr server")
        return result

    def wanted_missing(self, page_size: int = 250) -> dict[str, Any]:
        self.LOGGER.info(f"🔍 Searching for missing videos.")
        headers = {"X-Api-Key": self._config.ApiKey}
        params = {"page": 1, "pageSize": page_size}
        resp = self.session.get(self.GetEndpoint(self.EndpointType.wanted), headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        self.LOGGER.info(f"📺 Found {len(result.get('records', []))} missing {self.ProperNames.lower()}.")
        return result

    def queue(self, page_size: int = 250) -> dict[str, Any]:
        self.LOGGER.info(f"🔍 Searching for queued videos.")
        headers = {"X-Api-Key": self._config.ApiKey}
        params = {"page": 1, "pageSize": page_size}
        resp = self.session.get(self.GetEndpoint(self.EndpointType.queue), headers=headers, params=params, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        self.LOGGER.info(f"📺 Found {len(result.get('records', []))} queued {self.ProperNames.lower()}.")
        return result

    # TODO: Why is this unused?
    def lookup_video(self, external_id: str) -> dict[str, Any]:
        external_db = self.ExternalDb
        self.LOGGER.info(f"🔍 Looking for {self.ProperName} using database {external_db}.")
        url = f"{self.GetEndpoint(self.EndpointType.api)}?{external_db}Id={external_id}"
        headers = {"X-Api-Key": self._config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        self.LOGGER.info(f"📺 Looked up {self.ProperName} from {self.ServerName} server: {resp.get('title')}")
        return resp.json()

    def get_video(self, item_id: str) -> dict[str, Any]:
        self.LOGGER.info(f"🔍 Fetching {self.ProperName} from {self.ServerName} server.")
        url = f"{self.GetEndpoint(self.EndpointType.api)}/{item_id}"
        headers = {"X-Api-Key": self._config.ApiKey}
        resp = self.session.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        self.LOGGER.info(f"📺 Fetched {self.ProperName} from {self.ServerName} server: {data.get('title')}")
        return data

    def update_rss(self) -> dict[str, Any]:
        headers = {"X-Api-Key": self._config.ApiKey}
        body = {
            "name": "RssSync"
        }
        self.LOGGER.info(f"🌐 Sending RSS sync command to {self.ServerName} server.")
        resp = self.session.post(self.GetEndpoint(self.EndpointType.command), headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def add_torznab_indexer(self):
        YORZNAB = AppSettings(filename='yorznab.yaml')
        payload = {
            "name": YORZNAB.get('feed', 'title'),
            "implementation": "Torznab",
            "implementationName": "Torznab",
            "configContract": "TorznabSettings",
            "infoLink": YORZNAB.get('feed', 'link'),
            "enableRss": True,
            "enableAutomaticSearch": True,
            "enableInteractiveSearch": True,
            "priority": 25,
            "tags": [],
            "fields": [
                {"name": "baseUrl", "value": YORZNAB.get('feed', 'link')},
                {"name": "apiKey", "value": KeyStore.get_key('INDEXER_KEY')},
                {"name": "apiPath", "value": YORZNAB.get('server', 'api_endpoint')},
                {"name": "categories", "value": [2000, 2010, 2020, 2030, 2040, 2045, 2050, 2060]},
                {"name": "minimumSeeders", "value": 1},
                {"name": "seedCriteria.seedTime", "value": 0},
                {"name": "seedCriteria.seedRatio", "value": 0.0},
                {"name": "rejectBlocklistedTorrentHashesWhileGrabbing", "value": False}
            ]
        }
        
        response = requests.post(
            self.GetEndpoint(self.EndpointType.indexer),
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self._config.ApiKey
            },
            json=payload
        )
        
        return response.json()
