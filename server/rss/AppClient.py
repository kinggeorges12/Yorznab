from abc import ABC, abstractmethod
from typing import Any
import httpx

class AppClient(ABC):
    """Abstract base class for all API clients"""
    
    _session: httpx.Client | None = None
    
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