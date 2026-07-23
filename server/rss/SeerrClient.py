from dataclasses import dataclass
import os
from typing import Optional

from dacite import MissingValueError, from_dict

# Import classes
from server import PROJECT_ROOT
from server.rss.AppClient import AppClient
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings, AppSettingsUndefined


@dataclass
class SeerrConfig:
    ServerType: str
    Url: str
    ApiKey: str
    UrlFrom: Optional[str] = None
    TypeName: Optional[str] = None

@dataclass
class SeerrClient(AppClient):
    
    def __init__(self):
        # Initialize qBittorrent client defaults
        self._name: str = "Seerr"
        self._config_file = "settings.yaml"
        self._config: SeerrConfig = None

        self.LOGGER = CustomLogger(name=self.Name)
        # Resolve config file settings.yaml
        try:
            config_raw = AppSettings(filename=self._config_file).exists(name=self.Name).get(key=self.Name, exists=True)
        except AppSettingsUndefined as e:
            self.LOGGER.error(f"☠️ Critical error: unable to continue without {self.Name}.")
            raise Exception(e)
        config_raw["ServerType"] = self.Name # Required field
        try:
            self._config = from_dict(data_class=SeerrConfig, data=config_raw)
        except MissingValueError as e: # dacite.exceptions.MissingValueError: missing value for field "Url"
            self.LOGGER.error(f"☠️ Trouble parsing field for {self.Name}, check file: {os.path.join(PROJECT_ROOT, self._config_file)}")
            raise Exception(e)