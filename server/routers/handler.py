import os
from pathlib import PurePosixPath
from threading import Lock

# Import modules
from server import SERVER_DIR
from server.utils.settings import AppSettings

class RouteHandler:
    
    _instance = None
    _lock = Lock()
    
    API, LOGIN, STATUS, STATIC, WEBHOOK, STATIC_DIR = None, None, None, None, None, None
    SERVER_DIR = SERVER_DIR
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        cls = self.__class__
        
        with self._lock:
            YORZNAB = AppSettings(filename='yorznab.yaml')
            cls.API = YORZNAB.get('server', 'api_endpoint') or "/api"
            cls.LOGIN = YORZNAB.get('server', 'login_endpoint') or "/login"
            cls.STATIC = YORZNAB.get('server', 'static_endpoint') or "/static"
            cls.STATUS = YORZNAB.get('server', 'status_endpoint') or "/status"
            cls.WEBHOOK = YORZNAB.get('server', 'webhook_endpoint') or "/webhook"
            cls.STATIC_DIR = os.path.join(cls.SERVER_DIR, "static")
            self._initialized = True

    @classmethod
    def get_static_url(cls, file: str = None) -> str:
        if file:
            return PurePosixPath(cls.STATIC, file)
        return cls.STATIC

    @classmethod
    def get_static_dir(cls, file: str = None) -> str:
        if file:
            return os.path.join(cls.STATIC_DIR, file)
        return cls.STATIC_DIR

RouteHandler()  # Initialize the singleton instance