
from __future__ import annotations
import os
from dataclasses import dataclass, field
from dacite import from_dict
import os
from pathlib import Path
import time
from typing import Any, Optional
import json
from threading import Lock
import yaml

# Import modules
from server.utils.config import ConfigFile
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings, AppSettingsUndefined

# Global logger instance
LOGGER = CustomLogger(name="feed", enable_log=True)

@dataclass
class FilterWeights:
    min_score: Optional[float] = None
    seeders_10pct: Optional[float] = None
    seeders_50pct: Optional[float] = None
    size_preferred: Optional[float] = None
    favorite: Optional[float] = None
    quality: Optional[float] = None

@dataclass
class FilterApp:
    category: Optional[list[dict[str, Optional[float]]]] = field(default_factory=list)
    weights: Optional[FilterWeights] = field(default_factory=FilterWeights)
    unknown_runtime: Optional[int] = None
    quality_search: Optional[list[str]] = field(default_factory=list)
    favorite_sites: Optional[list[str]] = field(default_factory=list)
    required_mbps: Optional[dict[str, float]] = field(default_factory=dict)
    best_mbps: Optional[dict[str, float]] = field(default_factory=dict)

@dataclass
class FilterTags:
    remove_jackett_tags: Optional[bool] = None
    tracker_tags_only: Optional[bool] = None
    tracker_tags_skip: Optional[bool] = None
    tracker_tags: Optional[dict[str, str]] = field(default_factory=dict)

@dataclass
class FeedFilter:
    file: Optional[str] = None
    tags: Optional[FilterTags] = field(default_factory=FilterTags)
    Movies: Optional[FilterApp] = field(default_factory=FilterApp)
    TV: Optional[FilterApp] = field(default_factory=FilterApp)

class FeedConfig:

    _lock = Lock()
    _instances: dict[str, FeedConfig] = {}
    _default_feed_config = "feed.yaml"
    _default_feed_folder: Path = Path(os.environ.get("FEED_DIR", "feeds"))
    
    def __new__(cls, config_file: str=_default_feed_config):  # pylint: disable=unused-argument
        with cls._lock:
            if config_file not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[config_file] = instance
        return cls._instances[config_file]

    def __init__(self, config_file: str=_default_feed_config):
        # prevent re-loading on repeated calls
        if getattr(self, "_initialized", False):
            return

        self._config_file = config_file or self.__class__._default_feed_config
        self._config = None
        self._config_settings = None
        self._feed_folder = self.__class__._default_feed_folder
        self._feed_file = Path(self._config_file).with_suffix(".json").name
        try:
            # Check if config file exists
            self._config_settings = AppSettings(self._config_file)
            self._config = from_dict(data_class=FeedFilter, data=self._config_settings.get())
            # Check for the feed file setting
            self._feed_file = self._config.file or self._feed_file
        except AppSettingsUndefined as e:
            LOGGER.warning(f"⚠️ {e}")
            LOGGER.warning(f"⚠️ Using default settings for feed.")
        self._config = self._config if self._config else FeedFilter()
        self._feed_path = Path(os.path.join(self._feed_folder, self._feed_file))
        self._cached_json = None
        self._initialized = True

    @classmethod
    def feed(cls, name = None) -> Path:
        """Get the paths to all feed files"""
        # Return the default if it exists and then the first feed file if no name is provided
        if not name:
            feed_default = cls._instances[cls._default_feed_config] if cls._default_feed_config in cls._instances else None
            feed_first = next(iter(cls._instances.values())) if cls._instances else None
            feed = feed_default if feed_default else feed_first
            return feed.file
        # Match full filename or filename without extension
        for instance in cls._instances.values():
            filename = instance.file.rstrip('.json') if instance.file else None
            if filename == name or instance.file == name:
                return instance.file
        return None

    @property
    def config_name(self) -> str:
        """Get the name of the configuration file, e.g., feed.yaml"""
        return self.config_path.name

    @property
    def config_path(self) -> Path:
        """Get the path to the configuration file, e.g., /app/config/feed.yaml"""
        return ConfigFile(self._config_file).path

    @property
    def config(self) -> FeedFilter:
        """Get the configuration, e.g., FeedFilter object"""
        return self._config

    @property
    def file(self) -> Path:
        """Get the filename of the feed file, e.g., feed.json"""
        return self._feed_file

    @property
    def path(self) -> Path:
        """Get the path to the feed file, e.g., feeds/feed.json"""
        return self._feed_path

    @property
    def exists(self) -> bool:
        """Check if the configuration file exists"""
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

    def save(self, data: Any) -> None:
        if not self.exists:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @property
    def file_age(self) -> float:
        """
        Get the age of the feed file in seconds.
        
        Returns:
            Age in seconds, or float('inf') if file doesn't exist
        """
        if not self.exists:
            return float('inf')
        
        file_mtime = os.path.getmtime(self.path)
        current_time = time.time()
        age_seconds = current_time - file_mtime
        
        return age_seconds

    def __str__(self):
        return f"FeedConfig(config={self.config_path}, feed={self.path})"