import secrets
from fastapi import Request

# Import modules
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings


LOGGER = CustomLogger(name="LoginService")
SETTINGS = AppSettings(filename='yorznab.yaml')
ID_NAME = "SECURE_APPID"
TITLE = SETTINGS.get('feed', 'title') or "Yorznab"

def authenticated(request: Request) -> bool:
    return request.cookies.get("authenticated") == "true"

def get_csrf_token() -> str:
    return secrets.token_hex(16)

def page_template(title: str, content: str, token: str,
                  css: str = None, js: str = None) -> str:
        
    return f'''<!DOCTYPE html>
<html>
    <head>
        <title>{TITLE} {title}</title>
        <link rel="stylesheet" href="{RouteHandler.STATIC}/css/web.css?token={token}">
        {f'<link rel="stylesheet" href="{RouteHandler.STATIC}/css/{css}?token={token}">' if css else ''}
        <script src="{RouteHandler.STATIC}/js/web.js?token={token}"></script>
        <script src="{RouteHandler.STATIC}/js/theme.js?token={token}"></script>
        {f'<script src="{RouteHandler.STATIC}/js/{js}?token={token}"></script>' if js else ''}
        <meta name="cache-control" content="no-cache, no-store, must-revalidate">
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>{content}</body>
</html>'''

def navigation(current_route: str = '') -> str:
    nav_items = [
        (f"{RouteHandler.LOGIN}/success", "🏠", "Home", "home-btn"),
        (f"{RouteHandler.LOGIN}/keys", "🔐", "Credentials", "creds-btn"),
        (f"{RouteHandler.LOGIN}/setup", "⚙️", "Configuration", "config-btn"),
    ]
    
    buttons = ""
    for route, emoji, label, cls in nav_items:
        active = " active" if current_route == route or current_route in route else ""
        buttons += f'''
            <button class="{cls}{active}" onclick="window.location.href='{route}'">
                {emoji} <span class="btn-label">{label}</span>
            </button>'''
    
    logout = f'''
            <form method="POST" action="{RouteHandler.LOGIN}/logout">
                <button type="submit" class="logout-btn">⏻ <span class="btn-label">Logout</span></button>
            </form>'''
    
    return f'''
        <div class="nav-actions">
            {buttons if current_route else ''}
            <button class="theme-toggle-btn" onclick="toggleTheme()">
                <span class="btn-icon">🌙</span>
                <span class="btn-label">Dark</span>
            </button>
            {logout if current_route else ''}
        </div>'''