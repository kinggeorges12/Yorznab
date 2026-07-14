from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import secrets
from typing import List, Union
from fastapi import HTTPException

import httpx
from websockets import Router

# Import modules
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.utils.settings import AppSettings


LOGGER = CustomLogger(name="LoginService")
SETTINGS = AppSettings(filename='yorznab.yaml')
ID_NAME = "LOGIN_PASSKEY"
TITLE = SETTINGS.get('feed', 'title') or "Yorznab"

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
        load_sources += f'<link rel="stylesheet" href="{RouteHandler.STATIC}/{css_file}?token={token}">' if css_file else ''
    for module_file, module_import in module.items():
        if module_file and module_import:
            load_sources += f'''<script type="module">
            import {module_import} from "{RouteHandler.STATIC}/{module_file}?token={token}"
            window.{module_import} = {module_import};
        </script>'''
        else:
            load_sources += f'<script type="module" src="{RouteHandler.STATIC}/{module_file}?token={token}"></script>' if module_file else ''
    for js_file in js:
        load_sources += f'<script src="{RouteHandler.STATIC}/{js_file}?token={token}"></script>' if js_file else ''

    return f'''<!DOCTYPE html>
<html>
    <head>
        <title>{TITLE} {title}</title>
        <script src="{RouteHandler.STATIC}/js/theme.js?token={token}"></script>
        <link rel="preload" href="{RouteHandler.STATIC}/css/web.css?token={token}" as="style">
        <link rel="stylesheet" href="{RouteHandler.STATIC}/css/web.css?token={token}">
        <script src="{RouteHandler.STATIC}/js/web.js?token={token}"></script>
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

def fetch_external_file(external_url: str) -> bytes:
    """
    Download a file from external URL and return raw bytes
    """
    with httpx.Client() as client:
        try:
            response = client.get(external_url)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=404, detail=f"External file not found: {e}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to external server: {e}")

def download_and_cache(url, file, cache_duration_hours=None):
    """
    Download a file and cache it locally
    """
    static_file = RouteHandler.get_static(file)
    cache_file = Path(static_file)
    LOGGER.debug(f"Loading from cache: {cache_file}")
    # Check if cache exists and is fresh
    cache_ready = False
    if os.path.exists(cache_file):
        cache_ready = True
        if cache_duration_hours is not None:
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
            cache_ready = file_age < timedelta(hours=cache_duration_hours)
    if not cache_ready:
        # Download fresh data
        LOGGER.debug(f"Downloading from: {url}")
        content_bytes = fetch_external_file(url)
        
        # Save to cache
        LOGGER.debug(f"Caching to: {cache_file}")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if content is JSON or binary
        try:
            # Try to parse as JSON
            data = json.loads(content_bytes)
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Save as binary
            with open(cache_file, 'wb') as f:
                f.write(content_bytes)
    
    return file
