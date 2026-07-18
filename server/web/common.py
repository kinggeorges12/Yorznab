import re
import secrets
from typing import List, Union

# Import modules
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings


LOGGER = CustomLogger(name="LoginService")
ID_NAME = "LOGIN_PASSKEY"
TITLE = AppSettings(filename='yorznab.yaml').get('feed', 'title') or "Yorznab"

def get_csrf_token() -> str:
    return secrets.token_hex(16)

def page_template(title: str, content: str, token: str,
                  css: Union[str, List[str]] = None,
                  module: dict[str,tuple[str,str]] = None,
                  js: Union[str, List[str]] = None) -> str:
    # Convert single string to list for consistent handling
    css = ([css] if isinstance(css, str) else css) if css is not None else []
    module = module if module is not None else {}
    js = ([js] if isinstance(js, str) else js) if js is not None else []
    
    load_sources = ''
    for css_file in css:
        if css_file.startswith(("https://", "http://")):
            load_sources += f'<link rel="stylesheet" type="text/css" href="{css_file}">'
        else:
            load_sources += f'<link rel="stylesheet" type="text/css" href="{RouteHandler.get_static_url(css_file)}?token={token}" >' if css_file else ''
    for module_file, module_imports in module.items():
        # Module imports should be an array or None for the default
        if module_imports:
            module_import_string = '{' + ', '.join(module_imports) + '}'
        else:
            module_import_string = re.sub(r'^.*/?([^./]+)[^/]*$', r'\1', module_file)  # Remove .min.js extension for default import
        if module_file:
            load_sources += f'''<script type="module">
            import {module_import_string} from "{RouteHandler.get_static_url(module_file)}?token={token}"
            {'; '.join(f"window.{import_name} = {import_name}" for import_name in module_imports)}
        </script>'''
        else:
            load_sources += f'<script type="module" src="{RouteHandler.get_static_url(module_file)}?token={token}"></script>' if module_file else ''
    for js_file in js:
        load_sources += f'<script src="{RouteHandler.get_static_url(js_file)}?token={token}"></script>' if js_file else ''

    return f'''<!DOCTYPE html>
<html>
    <head>
        <title>{TITLE} {title}</title>
        <script src="{RouteHandler.get_static_url('js/theme.js')}?token={token}"></script>
        <link rel="preload" href="{RouteHandler.get_static_url('css/web.css')}?token={token}" as="style">
        <link rel="stylesheet" href="{RouteHandler.get_static_url('css/web.css')}?token={token}">
        <script src="{RouteHandler.get_static_url('js/web.js')}?token={token}"></script>
        {load_sources}
        <meta name="cache-control" content="no-cache, no-store, must-revalidate">
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>{content}</body>
</html>'''

def navigation(current_route: str = '') -> str:
    nav_items = [
        (f"{RouteHandler.LOGIN}/home", "🏠", "Home", "home-btn"),
        (f"{RouteHandler.LOGIN}/keys", "🔐", "Credentials", "creds-btn"),
        (f"{RouteHandler.LOGIN}/setup", "⚙️", "Configuration", "config-btn"),
        (f"{RouteHandler.LOGIN}/feeds", "📻", "Feeds", "feed-btn"),
    ]
    
    buttons = ""
    for route, emoji, label, cls in nav_items:
        active = " active" if current_route == route or current_route in route else ""
        buttons += f'''
            <button class="{cls}{active}" onclick="window.location.href='{route}'">
                {emoji} <span class="btn-label">{label}</span>
            </button>'''
    
    return f'''
        <div class="nav-actions">
            {buttons if current_route else ''}
            <button class="theme-toggle-btn" onclick="toggleTheme()">
                <span class="btn-icon">🌙</span>
                <span class="btn-label">Dark</span>
            </button>
        </div>'''
