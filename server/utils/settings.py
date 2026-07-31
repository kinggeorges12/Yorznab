from __future__ import annotations
from typing import Any, Callable, Self
import yaml
from threading import Lock

from server.utils.config import ConfigFile

class AppSettingsUndefined(Exception):
    """Exception raised when a library is not defined or configured."""
    pass

class AppSettings:
    _instances: dict[str, AppSettings] = {}
    _lock = Lock()

    def __new__(cls, filename: str, *args, **kwargs) -> AppSettings:
        with cls._lock:
            if filename not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[filename] = instance
        return cls._instances[filename]

    def __init__(self, filename: str, on_change_callback: Callable = None, prop_type_callback: Callable = None):
        # prevent re-loading on repeated calls
        if getattr(self, "_initialized", False):
            return
        self._config_file = ConfigFile(filename)
        self.load()
        self._initialized = True
        self._prop_type = prop_type_callback
        self._on_change = on_change_callback

    def load(self) -> None:
        path = self._config_file.path

        if path.exists():
            with open(path, "r") as f:
                self._data = yaml.safe_load(f) or {}
                return

        self._data = {}
    
    def save(self) -> None:
        """Save the current data back to the YAML file."""
        path = self._config_file.path
        with open(path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

    def set(self, config_dict: dict[str, str]) -> None:
        """Set configuration values for existing keys only.
        
        Usage:
            config.set({
                'Server: Port': 8080,
                'Server: Host': 'localhost',
                'Database: Host': 'db.example.com'
            })
        """
        updated = False
        
        for key_path, value in config_dict.items():
            if self._set_if_exists(key_path, value):
                updated = True
        
        if updated:
            self.save()
            if self._on_change:
                self._on_change()

    def _set_if_exists(self, key_path: str, value: Any) -> bool:
        """Set a value only if the key exists and the value is different.
        
        Returns:
            bool: True if the key existed and was updated with a new value, False otherwise.
        """
        keys = [k.strip() for k in key_path.split(':')]
        data = self._data
        
        # Navigate to find/create the parent
        for key in keys[:-1]:
            if key not in data or not isinstance(data[key], dict):
                data[key] = {}  # Create parent if it doesn't exist
            data = data[key]
        
        parsed_key = keys[-1]
        
        # Get the prop type and convert the data
        prop_type = self._prop_type(parsed_key)
        if prop_type:
            value = prop_type(value)
        else:
            # Property does not exist in config
            return False
        
        # Check if value actually changed (key might not exist yet)
        if parsed_key in data and data[parsed_key] == value:
            return False  # No change needed
        
        # Value is different or key doesn't exist, update it
        data[parsed_key] = value
        return True
            
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
    
    def exists(self, name: str = None) -> Self:
        """Check if the configuration file exists"""
        if not self._config_file.path.exists():
            raise AppSettingsUndefined(f"The file for {name or 'this'} does not exist: {self._config_file.path}")
        return self

    @classmethod
    def reset(cls) -> None:
        """Reset all instances of AppSettings."""
        with cls._lock:
            for instance in cls._instances.values():
                instance._initialized = False
                
        for instance in cls._instances.values():
            instance._callback()