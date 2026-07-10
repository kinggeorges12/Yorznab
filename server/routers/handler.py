from threading import Lock

# Import modules
from server.utils.settings import AppSettings

SETTINGS = AppSettings(filename='yorznab.yaml')

class RouteHandlerFactory:
    
    _instance = None
    _lock = Lock()
    
    API, LOGIN, STATUS, STATIC, WEBHOOK = None, None, None, None, None
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        
        with self._lock:
            self.API = SETTINGS.get('server', 'api_endpoint') or "/api"
            self.LOGIN = SETTINGS.get('server', 'login_endpoint') or "/login"
            self.STATIC = SETTINGS.get('server', 'static_endpoint') or "/static"
            self.STATUS = SETTINGS.get('server', 'status_endpoint') or "/status"
            self.WEBHOOK = SETTINGS.get('server', 'webhook_endpoint') or "/webhook"
            self._initialized = True

# Initialize routes
RouteHandler = RouteHandlerFactory()