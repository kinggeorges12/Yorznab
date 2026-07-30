from abc import ABC, abstractmethod
from dataclasses import dataclass
import os
from typing import Any
import httpx

class AppClient(ABC):
    """Abstract base class for all API clients"""
    
    _session: httpx.Client | None = None
    _config_folder: str = "applications"

    def __init__(self, name: str = None):
        self._name = name
        self._config = None
        self._config_filename: str = f"{self._name}.yaml"
        self._config_file = os.path.join(self._config_folder, self._config_filename)
    
    @property
    def DefaultUrl(self) -> str:
        """Base URL"""
        pass
    
    @property
    def Version(self) -> str: return self.status().get("version", '?')
    
    @property
    def Config(self) -> dataclass: return self._config
    
    @property
    @abstractmethod
    def ServerName(self) -> str:
        """Client name"""
        pass
    
    @property
    @abstractmethod
    def Url(self) -> str:
        """Base URL"""
        pass
    
    @property
    @abstractmethod
    def ApiVersion(self) -> str:
        """API version path"""
        pass
    
    @property
    def UrlPath(self) -> str:
        """Full URL with API version"""
        return self.Url + self.ApiVersion
    
    @classmethod
    def _get_session(cls) -> httpx.Client:
        """Get or create singleton session"""
        if cls._session is None:
            cls._session = httpx.Client()
        return cls._session
    
    @abstractmethod
    def session(self) -> httpx.Client:
        """Get the session"""
        pass
    
    @abstractmethod
    def status(self) -> dict[str, Any] | str:
        """Check server status"""
        pass