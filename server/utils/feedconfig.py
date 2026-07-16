
from __future__ import annotations
import datetime
from glob import glob
import os
from dataclasses import asdict, dataclass, field
from dacite import from_dict
import os
from pathlib import Path
import time
from typing import Any, List, Optional
import json
from threading import Lock

import yaml

# Import modules
from server.utils.config import ConfigFile
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings, AppSettingsUndefined
from server.utils.timezoneaware import TimezoneAware

# Global logger instance
LOGGER = CustomLogger(name="feed")

@dataclass
class FilterWeights:
    min_score: Optional[float] = None
    seeders_10pct: Optional[float] = None
    seeders_50pct: Optional[float] = None
    size_preferred: Optional[float] = None
    favorite: Optional[float] = None
    quality: Optional[float] = None

@dataclass
class FilterRange:
    lower: Optional[float] = None
    upper: Optional[float] = None

@dataclass
class FilterApp:
    category: Optional[list[dict[str, Optional[float]]]] = field(default_factory=list)
    weights: Optional[FilterWeights] = field(default_factory=FilterWeights)
    unknown_runtime: Optional[int] = None
    quality_search: Optional[list[str]] = field(default_factory=list)
    favorite_sites: Optional[list[str]] = field(default_factory=list)
    required_mbps: Optional[FilterRange] = field(default_factory=FilterRange)
    best_mbps: Optional[FilterRange] = field(default_factory=FilterRange)

@dataclass
class FilterTags:
    remove_jackett_tags: Optional[bool] = None
    tracker_tags_only: Optional[bool] = None
    tracker_tags_skip: Optional[bool] = None
    tracker_tags: Optional[dict[str, str | None]] = field(default_factory=dict)

@dataclass
class FeedFilter:
    tags: Optional[FilterTags] = field(default_factory=FilterTags)
    Movies: Optional[FilterApp] = field(default_factory=FilterApp)
    TV: Optional[FilterApp] = field(default_factory=FilterApp)

class FeedConfig:

    _lock = Lock()
    _instances: dict[str, FeedConfig] = {}
    _feed_config_folder: str = 'feeds' # /app/config/feeds
    _default_feed_name = "myfeed"
    _default_feed_folder: Path = Path(os.environ.get("DB_DIR", "database")) # /app/database
    
    def __new__(cls, feed_name: str=_default_feed_name):  # pylint: disable=unused-argument
        with cls._lock:
            if feed_name not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[feed_name] = instance
        return cls._instances[feed_name]

    def __init__(self, feed_name: str=_default_feed_name):
        # prevent re-loading on repeated calls
        if getattr(self, "_initialized", False):
            return

        self._feed_name = feed_name or self._default_feed_name
        self._config_file = f"{self._feed_name}.yaml" # myfeed.yaml
        self._config_path = os.path.join(self._feed_config_folder, self._config_file) # feeds/myfeed.yaml
        self._config_settings = None
        try:
            # Check if config file exists
            self._config_settings = AppSettings(self._config_path)
            self._config_settings.exists('FeedConfig')
        except AppSettingsUndefined as e:
            LOGGER.warning(f"⚠️ {e}")
            LOGGER.warning(f"⚠️ Using default settings for feed.")
        self._config = self.load(self._config_settings.get() if self._config_settings else None)
        self._feed_file = f"{self._feed_name}.json"
        self._feed_folder = self.__class__._default_feed_folder
        self._feed_path = Path(os.path.join(self._feed_folder, self._feed_file))
        self._cached_json = None
        self._initialized = True

    def load(self, data: dict[str, Any] = None) -> FeedFilter:
        """Create a new feed configuration file with optional initial data"""
        feed_filter = FeedFilter()
        if data is not None:
            feed_filter = from_dict(data_class=FeedFilter, data=data)
        self._config = feed_filter
        return feed_filter

    def save(self, yaml_content: str) -> None:
        """Save raw YAML content to a file"""
        config_path = self.config_path # /app/config/feeds/feed.yaml
        if not self.exists:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            LOGGER.debug(f"✅ Created new feed configuration: {config_path}")
        else:
            LOGGER.warning(f"⚠️ Feed configuration '{self.feed_name}' already exists: {config_path}")
            new_config_path = os.path.join(f"{config_path}-{TimezoneAware('%Y-%m-%d_%H-%M-%S')}.bak")
            os.rename(config_path, new_config_path)
            LOGGER.warning(f"⚠️ Moved existing configuration '{self.feed_name}' to: {new_config_path}")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(yaml_content)

    @classmethod
    def feeds(cls, values: str=None) -> List[FeedConfig]:
        if values is None:
            feed_config_pattern = ConfigFile(os.path.join(cls._feed_config_folder, "*.yaml"))
            print(f"Searching for feed configuration files in: {feed_config_pattern.path}")
            feed_files = glob(str(feed_config_pattern.path.as_posix()))
            print(f"Found feed configuration files: {feed_files}")
            for feed_file in feed_files:
                feed_name = Path(feed_file).stem
                cls(feed_name)
            return list(cls._instances.values())
        feed_arr = (values).split(',')
        feed_cleaned = [feed_name.strip() for feed_name in feed_arr]
        return list([cls(feed_name) for feed_name in feed_cleaned])

    @classmethod
    def feed(cls, name = None) -> FeedConfig:
        """Get the paths to all feed files"""
        # Return the default if it exists and then the first feed file if no name is provided
        if not name:
            feed_default = cls._instances[cls._default_feed_name] if cls._default_feed_name in cls._instances else None
            feed_first = next(iter(cls._instances.values())) if cls._instances else None
            feed = feed_default if feed_default else feed_first
            return feed.file
        # Match full filename or filename without extension
        if name in cls._instances.keys():
            return cls._instances[name]
        return None
    
    @property
    def feed_name(self) -> str:
        """Get the name of the configuration file, e.g., myfeed"""
        return self._feed_name
    
    @property
    def feed_filename(self) -> str:
        """Get the name of the configuration file, e.g., myfeed"""
        return self._config_file

    @property
    def config_path(self) -> Path:
        """Get the path to the configuration file, e.g., /app/config/feed.yaml"""
        return ConfigFile(self._config_path).path

    @property
    def config(self) -> FeedFilter:
        """Get the configuration, e.g., FeedFilter object"""
        return self._config

    @property
    def file(self) -> Path:
        """Get the filename of the database file, e.g., feed.json"""
        return self._feed_file

    @property
    def path(self) -> Path:
        """Get the path to the database file, e.g., database/feed.json"""
        return self._feed_path

    @property
    def exists(self) -> bool:
        """Check if the database file exists"""
        return self._feed_path.exists() if self._feed_path else False

    def read(self, cache=False) -> Any:
        if not self.exists:
            return []
        if cache and hasattr(self, '_cached_json'):
            return self._cached_json

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cached_json = data
        except json.JSONDecodeError:
            LOGGER.error(f"🚨 Config path contains invalid JSON: {self.path}")
            return []

        return data

    def write(self, data: Any) -> None:
        if not self.exists:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def file_age(self) -> float:
        """
        Get the age of the database file in seconds.
        
        Returns:
            Age in seconds, or float('inf') if file doesn't exist
        """
        if not self.exists:
            return float('inf')
        
        file_mtime = os.path.getmtime(self.path)
        current_time = time.time()
        age_seconds = current_time - file_mtime
        
        return age_seconds

    def _debug(self):
        return f"""FeedConfig(_feed_name={self._feed_name},
_config_file={self._config_file},
_config_path={self._config_path},
_config_settings={self._config_settings},
_feed_folder={self._feed_folder},
_feed_file={self._feed_file},
_feed_path={self._feed_path})"""

    def __str__(self):
        return f"FeedConfig(config={self._feed_name}, feed={self._config_file})"