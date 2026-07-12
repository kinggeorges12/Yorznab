from __future__ import annotations
from typing import Self
import yaml
from threading import Lock

from server.utils.config import ConfigFile

class AppSettingsUndefined(Exception):
    """Exception raised when a library is not defined or configured."""
    pass

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
        self.load()
        self._initialized = True

    def load(self) -> None:
        path = self._config_file.path

        if path.exists():
            with open(path, "r") as f:
                self._data = yaml.safe_load(f) or {}
                return

        self._data = {}
    
    def get(self, key: str = None, sub: str = None, exists: bool = False) -> dict | None:
        if key is not None and sub is not None:
            return self._data.get(key, {}).get(sub, None)
        elif key is not None:
            data = self._data.get(key, None)
            if data is None and exists:
                raise AppSettingsUndefined(f"The configuration section for {key} is undefined or misconfigured.")
            return data
        return self._data
        
    def __str__(self) -> str:
        """Detailed string representation for debugging"""
        # Get all attributes including private ones
        attrs = {k: v for k, v in self.__dict__.items()}
        return f"AppSettings({attrs})"
    
    def exists(self, name: str) -> Self:
        """Check if the configuration file exists"""
        if not self._config_file.path.exists():
            raise AppSettingsUndefined(f"The file for {name} does not exist: {self._config_file.path}")
        return self