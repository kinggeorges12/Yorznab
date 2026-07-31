from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional
import httpx

# Import modules
from server.cron.CronRunner import CronRunner
from server.entities.BaseClient import BaseClient
from server.routers.handler import RouteHandler
from server.routers.status import cron_status
from server.utils.docs import HOST_URL

@dataclass
class YorznabConfig:
    ServerName: Optional[str] = field(
        default='Yorznab',
        metadata={
            "name": "Name",
            "description": "Name of the application and indexer"
        }
    )
    Url: Optional[str] = field(
        default=HOST_URL,
        metadata={
            "description": "External URL of the Yorznab instance"
        }
    )
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
            "description": "Number of days to retain files before cleanup",
            "min": 1,
            "max": 36500
        }
    )
    WebhookWait: Optional[int] = field(
        default=60,
        metadata={
            "name": "Webhook Wait",
            "description": "Seconds to wait for webhook to complete",
            "min": 0,
            "max": 3600
        }
    )

class YorznabClient(BaseClient[YorznabConfig]):

    _instance = None
    _lock = Lock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized: return
        # Initialize default config name
        super().__init__(name="Instance")

        CronRunner.send_wakeup()
        self._initialized = True

    # Default settings, unused by Indexers
    @property
    def Image(self) -> str: return self.Config.Url + '/static/banner.jpg'
    @property
    def Email(self) -> str: return 'admin@example.com'
    @property
    def Description(self) -> str: return 'Get yo feed on!'
    @property
    def Language(self) -> str: return 'en'
    
    @property
    def DefaultUrl(self) -> str: return HOST_URL
    
    @property
    def ApiVersion(self) -> str:
        """API version path"""
        return RouteHandler.API_v1
    
    def status(self) -> dict[str, Any] | str: return cron_status()

    # Unimplemented methods for BaseClient interface
    def session(self) -> httpx.Client: pass