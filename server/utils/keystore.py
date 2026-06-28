from threading import Lock
import uuid
import yaml

# Import classes
from server.utils.config import ConfigFile
KEY_LIST = ["API_KEY", "WEBHOOK_KEY", "UNIQUE_APPID"]

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

        self._config_file = ConfigFile("keys.yaml")
        self._keys = self._load_or_create_keys()
        self._initialized = True

    def _load_or_create_keys(self) -> dict[str, str]:
        isKeyGenerated = False
        if self._config_file.path.exists():
            with open(self._config_file.path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
        else:
            raw_config = {}

        keys = {}
        for key_name in KEY_LIST:
            key_value = raw_config.get(key_name)
            if not key_value:
                key_value = str(uuid.uuid4())
                isKeyGenerated = True
            keys[key_name] = key_value

        if isKeyGenerated:
            self._config_file.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._config_file.path, "w", encoding="utf-8") as f:
                yaml.safe_dump(keys, f, sort_keys=False)

        return keys

    @classmethod
    def get_key(cls, name: str, default: str = None) -> str:
        return cls.instance()._keys.get(name, default)
