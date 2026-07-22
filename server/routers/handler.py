import os
from pathlib import PurePosixPath
from threading import Lock

# Import modules
import server
from server.utils.settings import AppSettings

class RouteHandler:
    
    _instance = None
    _lock = Lock()
    
    SERVER_DIR = server.SERVER_DIR
    API = "/api"
    API_v1 = API + "/v1"
    FEED = API_v1 + "/feed"
    FEEDS = API_v1 + "/feeds"
    INDEXER = API_v1 + "/indexer"
    AUTH = API_v1 + "/auth"
    ROUTES = API_v1 + "/routes"
    STATUS = API_v1 + "/status"
    WEBHOOK = API_v1 + "/webhook"
    API_DEFAULT = INDEXER
    DASHBOARD = ""
    STATIC = "/static"
    STATIC_DIR = os.path.join(SERVER_DIR, "static")
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        
        with self._lock:
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