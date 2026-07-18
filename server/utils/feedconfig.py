
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
from server.utils.timeformatter import TimezoneAware

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
    unknown_runtime: Optional[float] = None
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

        self._config_settings = None
        if feed_name is not None:
            self._feed_name = feed_name or self._default_feed_name
            self._config_file = f"{self._feed_name}.yaml" # myfeed.yaml
            self._config_path = os.path.join(self._feed_config_folder, self._config_file) # feeds/myfeed.yaml
            try:
                # Check if config file exists
                self._config_settings = AppSettings(self._config_path)
                self._config_settings.exists('FeedConfig')
            except AppSettingsUndefined as e:
                LOGGER.warning(f"⚠️ {e}")
                LOGGER.warning(f"⚠️ Using default settings for feed.")
            self._feed_file = f"{self._feed_name}.json"
            self._feed_folder = self.__class__._default_feed_folder
            self._feed_path = Path(os.path.join(self._feed_folder, self._feed_file))
        self._config = self.load(self._config_settings.get() if self._config_settings else None)
        self._cached_json = None
        self._initialized = True

    def load(self, data: dict[str, Any] = None) -> FeedFilter:
        """Create a new feed configuration file with optional initial data"""
        feed_filter = FeedFilter()
        if data is not None:
            feed_filter = from_dict(data_class=FeedFilter, data=data)
        self._config = feed_filter
        return feed_filter

    @classmethod
    def delete(cls, feed_name: str) -> bool:
        """Delete the YAML configuration file"""
        feed_config = cls._instances.get(feed_name)
        if feed_config is not None:
            config_path = feed_config.config_path # /app/config/feeds/feed.yaml
            exists = config_path.exists()
        if config_path.exists():
            new_config_path = os.path.join(f"{config_path}-{TimezoneAware.filename()}.bak")
            os.rename(config_path, new_config_path)
            LOGGER.info(f"📦 Moved existing configuration '{feed_config.feed_name}' to: {new_config_path}")
        else:
            LOGGER.warning(f"⚠️ Feed configuration '{feed_config.feed_name}' does not exist: {config_path}")
        cls._instances.pop(feed_name, None)
        return exists

    @classmethod
    def save(cls, feed_name: str, yaml_data: str) -> FeedConfig:
        """
            Save raw YAML content to a file.
            Args:
                feed_name: The name of the feed
                yaml_data: Raw YAML string content
            Raises:
                YAMLError: If the YAML content is malformed or cannot be parsed
        """
        # Validate YAML and FeedFilter structure
        yaml_content = yaml.safe_load(yaml_data)
        feed_config = cls(feed_name=feed_name)
        feed_config.load(yaml_content)

        config_path = feed_config.config_path # /app/config/feeds/feed.yaml
        if not feed_config.exists:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
        else:
            LOGGER.warning(f"📑 Feed configuration '{feed_config.feed_name}' already exists: {config_path}")
            cls.delete(feed_name=feed_name)
        with open(config_path, "w", encoding="utf-8", newline='\n') as f:
            f.write(yaml_data)
        LOGGER.debug(f"✅ Created new feed configuration: {config_path}")
        return feed_config

    @classmethod
    def feeds(cls, values: str=None) -> List[FeedConfig]:
        feeds_arr = []
        if values is None:
            feed_config_pattern = ConfigFile(os.path.join(cls._feed_config_folder, "*.yaml"))
            feed_files = glob(str(feed_config_pattern.path.as_posix()))
            for feed_file in feed_files:
                feed_name = Path(feed_file).stem
                cls(feed_name=feed_name)
            LOGGER.debug(f"✅ Found {len(cls._instances)} feed configuration(s): {', '.join(cls._instances.keys())}")
            feeds_arr = list(cls._instances.values())
        else:
            feed_args = (values).split(',')
            for feed_name in feed_args:
                feed_config = cls(feed_name=feed_name.strip())
                try:
                    if feed_config and feed_config._config_settings:
                        # Check if the feed configuration file exists: config/feeds/feed.yaml
                        feed_config._config_settings.exists(name='FeedConfig')
                        feeds_arr.append(feed_config)
                except:
                    LOGGER.warning(f"⚠️ Feed configuration '{feed_name}' does not exist or is misconfigured.")
                    pass
            LOGGER.debug(f"✅ Parsed {len(feeds_arr)} feed configuration(s): {', '.join([feed.feed_name for feed in feeds_arr])}")
        return feeds_arr

    @classmethod
    def feed(cls, name = None) -> FeedConfig:
        """Get the paths to all feed files"""
        # Return the default if it exists and then the first feed file if no name is provided
        if not name:
            feed_default = cls._instances[cls._default_feed_name] if cls._default_feed_name in cls._instances else None
            feed_first = next(iter(cls._instances.values())) if cls._instances else None
            return feed_default if feed_default else feed_first
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
        with open(self.path, "w", encoding="utf-8", newline='\n') as f:
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
        return f"FeedConfig(name={self._feed_name}, feed={self._config_file}, database={self._feed_file})"