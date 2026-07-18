from pathlib import Path
import os

# Import modules
from server import PROJECT_ROOT

# Set default directory
CONFIG_DIR = os.getenv("CONFIG_DIR") or os.path.join(PROJECT_ROOT, "config")

"""Get the configuration directory path from the environment variable or default to /app/config"""
class ConfigFile:
    
    def __init__(self, file: str):
        file_path = os.path.join(CONFIG_DIR, file)
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