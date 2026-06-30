import os
import threading
import time
from typing import Any
import json
from threading import Lock

# Import modules
from server.utils.config import ConfigFile

FEED_FILE = "torrent.json"

class FeedFile:

    _instance = None
    _lock = Lock()

    @classmethod
    def instance(cls):
        return cls()
    
    def __new__(cls, filename=FEED_FILE):  # pylint: disable=unused-argument
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, filename=FEED_FILE):
        if not filename:
            filename = FEED_FILE
        with type(self)._lock:
            if (
                not getattr(self, "_initialized", False)
                or filename != self._filename
            ):
                self._config_file = ConfigFile(filename)
                self._filename = filename
                self._cached_json = None
                self._initialized = True

    @classmethod
    def exists(cls) -> bool:
        """Check if the torrent.json file exists."""
        # Do not initialize if no instance yet
        if not cls._instance or not getattr(cls._instance, "_initialized", False):
            return ConfigFile(FEED_FILE).path.exists()
        return cls._instance._config_file.path.exists()

    def read(self, cache=False) -> Any:
        if not self.exists():
            return []
        if cache and hasattr(self, '_cached_json'):
            return self._cached_json

        try:
            with open(self._config_file.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._cached_json = data
        except json.JSONDecodeError:
            print(f"Error: {self._config_file.path} contains invalid JSON.")
            return []

        return data

    def save(self, data: Any) -> None:
        if not self.exists():
            os.makedirs(os.path.dirname(self._config_file.path), exist_ok=True)
        with open(self._config_file.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_file_age(self) -> float:
        """
        Get the age of the feed file in seconds.
        
        Returns:
            Age in seconds, or float('inf') if file doesn't exist
        """
        if not self.exists():
            return float('inf')
        
        file_mtime = os.path.getmtime(self._config_file.path)
        current_time = time.time()
        age_seconds = current_time - file_mtime
        
        return age_seconds

    def __str__(self):
        return str(self._config_file.path)