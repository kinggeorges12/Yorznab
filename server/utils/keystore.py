import secrets
from threading import Lock
import yaml

# Import classes
from server.utils.config import ConfigFile
KEYS_ALL = ["API_KEY", "WEBHOOK_KEY", "UNIQUE_APPID", "LOGIN_PASSKEY"]
KEY_LOGIN = "LOGIN_PASSKEY"
KEY_FILE = "keys.yaml"

class KeyStore:
    _instance = None
    _lock = Lock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Don't auto-initialize keys in __init__
        if not hasattr(self, "_keys"):
            self._keys = {}
        if not hasattr(self, "_config_file"):
            self._config_file = ConfigFile(KEY_FILE)
        # Load keys if file exists and not already initialized
        if not self.__class__._initialized:
            self._load()

    def _generate(self) -> str:
        """Generate a new key without writing to file."""
        return "yz_" + secrets.token_urlsafe(16).rstrip("=")

    @classmethod
    def exists(cls) -> bool:
        """Check if the keys.yaml file exists."""
        return ConfigFile(KEY_FILE).path.exists()

    @classmethod
    def write_keys(cls, login_passkey: str = None):
        """Write the generated keys to the file."""
        instance = cls()

        with cls._lock:
            # Use user-provided login_passkey
            instance._keys[KEY_LOGIN] = login_passkey
            
            # Generate any missing keys
            for key_name in KEYS_ALL:
                if key_name not in instance._keys or not instance._keys[key_name]:
                    instance._keys[key_name] = instance._generate()
        
        # Write to file
        instance._config_file.path.parent.mkdir(parents=True, exist_ok=True)
        with open(instance._config_file.path, "w", encoding="utf-8") as f:
            yaml.safe_dump(instance._keys, f, sort_keys=False)
        
        # Mark as initialized since we now have all keys written
        instance._initialized = True

    def _load(self):
        """Load keys from the file."""
        
        if not self.exists():
            # File doesn't exist, generate temporary keys
            for key_name in KEYS_ALL:
                self._keys[key_name] = self._generate()
            # Don't mark as initialized - keys are temporary
            return
        
        # Load from file
        with open(self._config_file.path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
            
        # Load keys from file, generate missing ones if needed
        for key_name in KEYS_ALL:
            if key_name in raw_config and raw_config[key_name]:
                self._keys[key_name] = raw_config[key_name]
            else:
                # Missing key, generate temporary one
                self._keys[key_name] = self._generate()
        
        # Only mark as initialized if LOGIN_PASSKEY exists in the file
        if KEY_LOGIN in raw_config and raw_config[KEY_LOGIN]:
            self.__class__._initialized = True

    @classmethod
    def is_ready(cls) -> bool:
        """Check if keys have been permanently initialized."""
        instance = cls()
        
        return instance._initialized

    @classmethod
    def get_key(cls, name: str) -> str:
        """Get a key by name. Throws error if key not found."""
        instance = cls()
        
        key_value = instance._keys.get(name)
        if key_value is None:
            raise KeyError(f"Key '{name}' not found. Make sure it exists in {KEY_FILE}")
        return key_value