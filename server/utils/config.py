from pathlib import Path
import os

"""Get the configuration directory path from the environment variable or default to /app/config"""
class ConfigFile:
    def __init__(self, file: str):
        config_dir = os.getenv("CONFIG_DIR", "/app/config")
        file_path = os.path.join(config_dir, file)
        self._path = Path(file_path)

    def __str__(self):
        return str(self._path)

    def __repr__(self):
        return f"ConfigFile({self._path})"
    
    @property
    def exists(self) -> bool:
        return self._path.exists()

    @property
    def path(self):
        return self._path

    def __fspath__(self):
        return self._path