from __future__ import annotations
from dataclasses import dataclass, field
import os
from threading import Lock
from typing import Any, Optional

from dacite import MissingValueError, from_dict
import httpx

# Import modules
from server import PROJECT_ROOT
from server.entities.AppClient import AppClient
from server.routers.handler import RouteHandler
from server.utils.settings import AppSettings, AppSettingsUndefined


@dataclass
class Cron:
    Schedule: Optional[str] = field(
        default='R */7 * * *',
        metadata={
            "description": "Cron schedule for when to run the job"
        }
    )
    RetentionDays: Optional[int] = field(
        default=90,
        metadata={
            "name": "Retention Days",
            "description": "Number of days to retain files before cleanup"
        }
    )
    WebhookWait: Optional[int] = field(
        default=60,
        metadata={
            "name": "Webhook Wait",
            "description": "Seconds to wait for webhook to complete"
        }
    )

@dataclass
class Indexer:
    ServerName: Optional[str] = field(
        default='Yorznab',
        metadata={
            "name": "Name",
            "description": "Name of the application and indexer"
        }
    )
    Url: Optional[str] = field(
        default='http://localhost:9116',
        metadata={
            "description": "External URL of the Yorznab instance"
        }
    )

class YorznabConfig(AppClient):

    _instance: YorznabConfig = None
    _lock = Lock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self._name = 'Yorznab Configuration'
        self._config_file = 'yorznab.yaml'
        self.Cron = None
        self.Indexer = None
        try:
            config_raw = AppSettings(filename=self._config_file).get()
        except AppSettingsUndefined as e:
            self.LOGGER.error(f"☠️ Critical error: unable to continue without {self._name}.")
            raise Exception(e)
        try:
            self.Cron = from_dict(data_class=Cron, data=config_raw.get('Cron', {}))
            self.Indexer = from_dict(data_class=Indexer, data=config_raw.get('Indexer', {}))
        except MissingValueError as e: # dacite.exceptions.MissingValueError: missing value for field "Url"
            self.LOGGER.error(f"☠️ Trouble parsing field for {self._name}, check file: {os.path.join(PROJECT_ROOT, self._config_file)}")
            raise Exception(e)
        self._initialized = True

    # Default settings, unused by Indexers
    def Image(self) -> str: return self.Indexer.Url + '/static/banner.jpg'
    def Email(self) -> str: return 'admin@example.com'
    def Description(self) -> str: return 'Get yo feed on!'
    def Language(self) -> str: return 'en'
    
    @classmethod
    def Reset(cls) -> None: cls._initialized = False

    @property
    def ServerName(self) -> str:
        """Client name"""
        return self.Indexer.ServerName
    
    @property
    def Url(self) -> str:
        """Base URL"""
        return RouteHandler.API_v1
    
    @property
    def ApiVersion(self) -> str:
        """API version path"""
        return RouteHandler.API_v1

    # Unimplemented methods for AppClient interface
    def session(self) -> httpx.Client: pass
    def status(self) -> dict[str, Any] | str: pass