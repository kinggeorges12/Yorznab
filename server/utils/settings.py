from __future__ import annotations
import yaml
from threading import Lock

from server.utils.config import ConfigFile


class AppSettings:
    _instances: dict[str, AppSettings] = {}
    _lock = Lock()

    def __new__(cls, filename: str):
        with cls._lock:
            if filename not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[filename] = instance
        return cls._instances[filename]

    def __init__(self, filename: str):
        # prevent re-loading on repeated calls
        if getattr(self, "_initialized", False):
            return

        self._config_file = ConfigFile(filename)
        self._data = self._load()
        self._initialized = True

    def _load(self) -> dict:
        path = self._config_file.path

        if path.exists():
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}

        return {}
    
    def get(self, key: str = None, sub: str = None):
        if key is not None and sub is not None:
            return self._data.get(key, {}).get(sub, None)
        elif key is not None:
            return self._data.get(key, None)
        return self._data
        
    def __str__(self) -> str:
        """Detailed string representation for debugging"""
        # Get all attributes including private ones
        attrs = {k: v for k, v in self.__dict__.items()}
        return f"AppSettings({attrs})"