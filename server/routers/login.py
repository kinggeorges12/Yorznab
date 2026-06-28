from datetime import timedelta
from itertools import accumulate
import os
import random
import secrets
from fastapi import APIRouter, Query, Request, Cookie
from fastapi.responses import Response, RedirectResponse
from urllib.parse import parse_qs

from server.routers.handler import RouteHandler
from server.rss.QBitClient import QBitClient
from server.rss.ArrClient import ArrClient, ArrType
from server.utils.customlogger import CustomLogger
from server.utils.keystore import KeyStore
from server.utils.settings import AppSettings, AppSettingsUndefined

router = APIRouter()

# Config
LOGGER = CustomLogger(name="LoginService")
SETTINGS = AppSettings(filename='yorznab.yaml')
ID_NAME = "SECURE_APPID"
TITLE = SETTINGS.get('feed', 'title') or "Yorznab"

# Helpers
def validate_appid(appid: str) -> bool:
    return appid and appid == KeyStore.get_key(ID_NAME)

def get_csrf_token() -> str:
    return secrets.token_hex(16)

def authenticated(request: Request) -> bool:
    return request.cookies.get("authenticated") == "true"

def set_auth_cookies(response: RedirectResponse, appid: str):
    max_age = int(timedelta(hours=24).total_seconds())
    response.set_cookie("authenticated", "true", httponly=True, secure=True, samesite="lax", max_age=max_age)
    response.set_cookie("appid", appid, httponly=True, secure=True, samesite="lax", max_age=max_age)

def page_template(title: str, content: str, token: str, js: str = "login.js") -> str:
    return f'''<!DOCTYPE html>
<html>
    <head>
        <title>{title}</title>
        <link rel="stylesheet" href="{RouteHandler.STATIC}/login.css?token={token}">
        <script src="{RouteHandler.STATIC}/{js}?token={token}"></script>
        <meta name="cache-control" content="no-cache, no-store, must-revalidate">
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body>{content}</body>
</html>'''

def navigation(current_route: str) -> str:
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
    
    return f'''
        <div class="nav-actions">
            {buttons}
            <form method="POST" action="{RouteHandler.LOGIN}/logout">
                <button type="submit" class="logout-btn">⏻ <span class="btn-label">Logout</span></button>
            </form>
        </div>'''


# Routes
@router.get(RouteHandler.LOGIN)
async def login_page(request: Request, appid: str = Query(None), failed: bool = Query(False)):
    if authenticated(request):
        return RedirectResponse(url=f"{RouteHandler.LOGIN}/success", status_code=303)
    
    if validate_appid(appid):
        response = RedirectResponse(url=f"{RouteHandler.LOGIN}/success", status_code=303)
        set_auth_cookies(response, appid)
        return response
    
    token = get_csrf_token()
    error = f'''
<div class="error-container">
    <p class="error-message">Invalid API Key provided.</p>
    <p class="hint-message">Did you try setting the Docker environment variable "{ID_NAME}"?</p>
</div>''' if (failed or validate_appid(appid)) else ""
    
    content = f'''
        <div class="login-container">
            <h1>Welcome to {TITLE}</h1>
            <form autocomplete="off" method="POST" action="{RouteHandler.LOGIN}">
                <input type="hidden" name="csrf_token" value="{token}">
                <div class="form-group">
                    <label for="appid">Please enter your App ID to show API keys:</label>
                    <div class="password-wrapper">
                        <input type="password" autocomplete="off" id="{ID_NAME}" name="appid" placeholder="{ID_NAME}" required>
                        <button type="button" class="toggle-btn" id="toggleBtn" aria-label="Toggle password visibility">
                            <span class="eye-icon">👁️</span>
                        </button>
                    </div>
                </div>
                <button type="submit">Submit</button>
            </form>
            {error}
        </div>'''
    
    return Response(content=page_template(f"{TITLE} Login", content, token), status_code=200, media_type="text/html")


@router.post(RouteHandler.LOGIN)
async def login_submit(request: Request):
    body = await request.body()
    parsed = parse_qs(body.decode('utf-8'))
    appid = parsed.get('appid', [''])[0]
    csrf_token = parsed.get('csrf_token', [''])[0]
    
    if not csrf_token or len(csrf_token) != 32:
        return RedirectResponse(url=f"{RouteHandler.LOGIN}?failed=true", status_code=303)
    
    if validate_appid(appid):
        response = RedirectResponse(url=f"{RouteHandler.LOGIN}/success", status_code=303)
        set_auth_cookies(response, appid)
        LOGGER.debug(f"User authenticated. CSRF Token: {csrf_token}")
        return response
    
    LOGGER.error(f"User authentication failed. AppID: {appid}, CSRF Token: {csrf_token}")
    return RedirectResponse(url=f"{RouteHandler.LOGIN}?failed=true", status_code=303)


@router.get(f"{RouteHandler.LOGIN}/success")
async def login_success(request: Request):
    if not authenticated(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    
    token = get_csrf_token()

    # Generate random delays for the ASCII art animation
    random_delays = [round(random.uniform(0.1, 0.3) + round(random.expovariate(8)*2, 1), 1) for _ in range(11)] + [0.1]
    animation_timer = list(reversed(list(accumulate(random_delays))))
    content = f'''
        <div class="success-container">
            {navigation(f'{RouteHandler.LOGIN}/success')}
            <h1>{TITLE} 🏠 Home</h1>
            <div class="text-card">
                <h2>Welcome! You are logged in.</h2>
                <br>
                <p>Check out the GitHub repository for updates and information:</p>
                <a href="https://github.com/kinggeorges12/Yorznab" target="_blank" rel="noopener noreferrer">https://github.com/kinggeorges12/Yorznab</a>
                <br><br>
                <p>Stuck? Post an issue:</p>
                <a href="https://github.com/kinggeorges12/Yorznab/issues" target="_blank" rel="noopener noreferrer">ARRGH HELP ME!</a>
            </div>
            <div class="text-card">
            <div id="ascii-container"><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╔══════════════════════════════════════════════════════════════════════════════╗</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║                                                                              ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║     ██╗   ██╗ ██████╗ ██████╗ ███████╗███╗   ██╗ █████╗ ██████╗ ██╗          ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║     ╚██╗ ██╔╝██╔═══██╗██╔══██╗╚══███╔╝████╗  ██║██╔══██╗██╔══██╗██║          ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║      ╚████╔╝ ██║   ██║██████╔╝  ███╔╝ ██╔██╗ ██║███████║██████╔╝██║          ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║       ╚██╔╝  ██║   ██║██╔══██╗ ███╔╝  ██║╚██╗██║██╔══██║██╔══██╗╚═╝          ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║        ██║   ╚██████╔╝██║  ██║███████╗██║ ╚████║██║  ██║██████╔╝██╗          ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║        ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═════╝ ╚═╝          ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║══════════════════════════════════════════════════════════════════════════════║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║                                                                              ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║                                                    ...Welcome to Yorznab!    ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╚══════════════════════════════════════════════════════════════════════════════╝</pre>

            </div>
        </div>'''
    
    return Response(content=page_template(f"{TITLE} Home", content, token), media_type="text/html")


@router.get(f"{RouteHandler.LOGIN}/keys")
async def keys(authenticated: str = Cookie(None)):
    if authenticated != "true":
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    
    token = get_csrf_token()
    api_key = KeyStore.get_key('API_KEY')
    webhook_key = KeyStore.get_key('WEBHOOK_KEY')
    
    content = f'''
        <div class="success-container">
            {navigation(f'{RouteHandler.LOGIN}/keys')}
            <h1>{TITLE} 🔐 Credentials</h1>
            <div class="key-container">
                <div class="key-label">🔑 API Key for Radarr &amp; Sonarr</div>
                <div class="key-value" id="apiKey">{api_key}</div>
            </div>
            <div class="key-container">
                <div class="key-label">🔗 Webhook Key for Jellyseerr</div>
                <div class="key-value" id="webhookKey">{webhook_key}</div>
            </div>
            <div class="copy-actions">
                <button class="copy-btn" onclick="copyKey('apiKey')">🔑 Copy API Key</button>
                <button class="copy-btn" onclick="copyKey('webhookKey')">🔗 Copy Webhook Key</button>
            </div>
        </div>'''
    
    return Response(content=page_template(f"{TITLE} API Credentials", content, token), media_type="text/html")


@router.get(f"{RouteHandler.LOGIN}/setup")
async def setup(authenticated: str = Cookie(None)):
    if authenticated != "true":
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    
    token = get_csrf_token()

    try:
        radarr_client = ArrClient(ArrType.Radarr)
        radarr_status = radarr_client.status() if radarr_client else ""
        LOGGER.debug(f"Radarr Status: {radarr_status}")
    except AppSettingsUndefined as e:
        LOGGER.error(e)
        radarr_client = {}
        radarr_status = ""
    try:
        sonarr_client = ArrClient(ArrType.Sonarr)
        sonarr_status = sonarr_client.status() if sonarr_client else ""
        LOGGER.debug(f"Sonarr Status: {sonarr_status}")
    except AppSettingsUndefined as e:
        LOGGER.error(e)
        sonarr_client = {}
        sonarr_status = ""
    try:
        qbittorrent_client = QBitClient()
        qbittorrent_status = qbittorrent_client.version() if qbittorrent_client else ""
        LOGGER.debug(f"Qbittorrent Status: {qbittorrent_status}")
    except AppSettingsUndefined as e:
        LOGGER.error(e)
        qbittorrent_client = {}
        qbittorrent_status = ""
    server_path = os.getenv("PYTHONPATH")
    content = f'''
        <div class="success-container">
            {navigation(f'{RouteHandler.LOGIN}/setup')}
            <h1>{TITLE} ⚙️ Configuration</h1>

            <div class="text-card">
                <h2>Connected Apps</h2>
                
                <div class="app-icons-container">
                    <!-- Radarr -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if radarr_status else 'red-border-shadow' }">
                            <a href="{radarr_client.Url if radarr_client and radarr_client.Url else '#'}" target="_blank">
                                <img class="app-icon" alt="Radarr"
                                  src="https://github.com/Radarr/radarr.github.io/blob/master/logo/1024.png?raw=true">
                            </a>
                        </div>
                        <div class="app-info">
                            <span class="app-name">{radarr_client.ServerName if radarr_client and radarr_client.ServerName else 'Radarr'}</span>
                            <span class="app-version">{radarr_status['version'] if radarr_status and 'version' in radarr_status else '?'}</span>
                            <span class="status-dot { 'healthy' if radarr_status else 'unhealthy' }"></span>
                        </div>
                    </div>
                    
                    <!-- Sonarr -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if sonarr_status else 'red-border-shadow' }">
                            <a href="{sonarr_client.Url if sonarr_client and sonarr_client.Url else '#'}" target="_blank">
                                <img class="app-icon" alt="Sonarr"
                                  src="https://github.com/Sonarr/Sonarr/blob/main/Logo/1024.png?raw=true">
                            </a>
                        </div>
                        <div class="app-info">
                            <span class="app-name">{ sonarr_client.ServerName if sonarr_client and sonarr_client.ServerName else 'Sonarr' }</span>
                            <span class="app-version">{sonarr_status['version'] if sonarr_status and 'version' in sonarr_status else '?'}</span>
                            <span class="status-dot { 'healthy' if sonarr_status else 'unhealthy' }"></span>
                        </div>
                    </div>
                    
                    <!-- Qbittorrent -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if qbittorrent_status else 'red-border-shadow' }">
                            <a href="{qbittorrent_client.Url if qbittorrent_client and qbittorrent_client.Url else '#'}" target="_blank" rel="noreferrer">
                                <img class="app-icon" alt="Qbittorrent"
                                  src="https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png">
                            </a>
                        </div>
                        <div class="app-info">
                            <span class="app-name">{ qbittorrent_client.ServerName if qbittorrent_client and qbittorrent_client.ServerName else 'qBittorrent' }</span>
                            <span class="app-version">{qbittorrent_status or '?'}</span>
                            <span class="status-dot { 'healthy' if qbittorrent_status else 'unhealthy' }"></span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="error-container" style="display: {'flex' if not radarr_status or not sonarr_status or not qbittorrent_status else 'none'};">
                <p class="error-message">Some of the applications are not configured properly.</p>
                <p class="hint-message">Please login to your server and run the code from the command line.</p>
            </div>

            <div class="key-container">
                <div class="key-label">📋 Interactive Setup Script for { 'PowerShell' if os.name == 'nt' else 'Shell' }</div>
                <div class="key-value">{ f'cd {server_path} && ./setup.ps1' if os.name == 'nt'
                                         else f'cd {server_path} && chmod +x setup.sh && ./setup.sh' }</div>
            </div>
            <div class="copy-actions">
                <button class="copy-btn" onclick="copyKey('setupCommand')">📋 Copy Setup Command</button>
            </div>
        </div>'''
    
    return Response(content=page_template(f"{TITLE} Configuration", content, token, "setup.js"), media_type="text/html")


@router.post(f"{RouteHandler.LOGIN}/logout")
async def logout():
    response = RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    response.delete_cookie("authenticated")
    response.delete_cookie("appid")
    LOGGER.debug(f"User logged out, cookies cleared.")
    return response