from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass, fields
import html
import os
from typing import Any, Generic, Optional, TypeVar, Union, get_args, get_origin
from dacite import MissingValueError, from_dict
import httpx

from server import PROJECT_ROOT
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings, AppSettingsUndefined

D = TypeVar('D', bound=dataclass)

class BaseClient(ABC, Generic[D]):
    """Abstract base class for all API clients"""
    
    _session: httpx.AsyncClient | None = None
    TIMEOUT_DEFAULT: int = 60  # Default timeout for requests in seconds

    def __init__(self, name: str = None):
        self._name = name
        self._config_file: str = f"{self._name}.yaml"
        self._config: Optional[D] = None
        self._config_type = get_args(self.__class__.__orig_bases__[0])[0] if not hasattr(self, '_config_type') else self._config_type
        self.LOGGER = CustomLogger(name=self._name)

        # Load from file and initialize
        self.Reset()
    
    @property
    def DefaultUrl(self) -> str:
        """Base URL"""
        pass
    
    @property
    async def Version(self) -> str: return (await self.status()).get("version", '?')
    
    @property
    def Config(self) -> Optional[D]: return self._config
    
    @property
    def ServerConfigHtml(self) -> str: return html.escape(self._name)
    
    @property
    def ServerNameHtml(self) -> str: return html.escape(self.ServerName)
    
    @property
    def ServerName(self) -> str:
        """Client name"""
        return self.Config.ServerName if self.Config and hasattr(self.Config, 'ServerName') and self.Config.ServerName else self._name
    
    def Reset(self) -> None:
        """Reset initialization state to force init or re-login"""
        # Resolve config file settings.yaml
        try:
            app_config = AppSettings(filename=self._config_file,
                                     on_change_callback=self.Reset,
                                     prop_type_callback=self.get_property_type)
            app_config.exists() # Check if the config file exists, will raise AppSettingsUndefined if not
        except AppSettingsUndefined as e:
            self.LOGGER.warning(f"⚠️ {e}")
            self.LOGGER.warning(f"⚠️ Using default settings for {self._name}.")
            app_config.save()
        try:
            self._config = from_dict(data_class=self._config_type, data=app_config.get())
        except MissingValueError as e:
            self.LOGGER.error(f"🚩 Trouble parsing field for {self._name}, check file: {os.path.join(PROJECT_ROOT, self._config_file)}")
            raise Exception(e)
        
        self._initialized = False

    def get_property_type(self, name: str) -> type | None:
        """Get the type of a property in the config"""
        if self.Config is None:
            return None
        # Get the field from the dataclass
        for field in fields(self.Config):
            if field.name == name:
                field_type = field.type
                # If it's a Union (like Optional[str]), extract the non-None type
                if get_origin(field_type) is Union:
                    args = get_args(field_type)
                    # Get the first non-None type
                    non_none_types = [t for t in args if t is not type(None)]
                    if non_none_types:
                        return non_none_types[0]
                    return None
                return field_type
        return None

    @property
    @abstractmethod
    def DefaultUrl(self) -> str:
        """Default Base URL"""
        pass
    
    @property
    @abstractmethod
    def ApiVersion(self) -> str:
        """API version path"""
        pass
    
    @property
    def Url(self) -> str:
        """Full URL with API version"""
        return self.Config.Url
    
    @property
    def UrlPath(self) -> str:
        """Full URL with API version"""
        return self.Url + self.ApiVersion
    
    @classmethod
    def _get_session(cls) -> httpx.AsyncClient:
        """Get or create singleton session"""
        if cls._session is None:
            cls._session = httpx.AsyncClient(
                timeout=cls.TIMEOUT_DEFAULT,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        return cls._session
    
    @abstractmethod
    def session(self) -> httpx.AsyncClient:
        """Get the session"""
        pass
    
    @abstractmethod
    async def status(self) -> dict[str, Any] | str:
        """Check server status"""
        pass