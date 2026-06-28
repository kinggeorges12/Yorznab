import os
import secrets
from threading import Lock
import yaml

# Import classes
from server.utils.config import ConfigFile
KEYS_ALL = ["API_KEY", "WEBHOOK_KEY", "SECURE_APPID"]
KEYS_ENV = ["SECURE_APPID"]
KEY_FILE = "keys.yaml"

class KeyStore:
    _instance = None
    _lock = Lock()

    @classmethod
    def instance(cls):
        return cls()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return

        self._config_file = ConfigFile(KEY_FILE)
        self._keys = self._load_or_create_keys()
        self._initialized = True

    @classmethod
    def exists(cls) -> bool:
        """Check if the keys.yaml file exists."""
        return ConfigFile(KEY_FILE).path.exists()

    def _load_or_create_keys(self) -> dict[str, str]:
        isKeyGenerated = False
        if self._config_file.path.exists():
            with open(self._config_file.path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
        else:
            raw_config = {}

        keys = {}
        for key_name in KEYS_ALL:
            key_value = raw_config.get(key_name)
            if not key_value:
                key_value = "yz_" + secrets.token_urlsafe(16).rstrip("=")
                isKeyGenerated = True
            keys[key_name] = key_value

        if isKeyGenerated:
            self._config_file.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file.path, "w", encoding="utf-8") as f:
                yaml.safe_dump(keys, f, sort_keys=False)

        # Load temporary keys from environment variables if they exist
        for key_name in KEYS_ALL:
            if key_name in KEYS_ENV and os.getenv(key_name):
                temp_key_value = os.getenv(key_name)
                keys[key_name] = temp_key_value

        return keys

    @classmethod
    def get_key(cls, name: str, default: str = None) -> str:
        return cls()._keys.get(name, default)
