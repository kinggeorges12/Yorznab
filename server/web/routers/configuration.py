import os

from fastapi import APIRouter, Cookie, Response
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.rss.ArrClient import ArrClient, ArrType
from server.rss.QBitClient import QBitClient
from server.utils.settings import AppSettingsUndefined
from server.web.common import LOGGER, TITLE, get_csrf_token, navigation, page_template

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/setup")
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
        LOGGER.debug(f"qBittorrent Status: {qbittorrent_status}")
    except AppSettingsUndefined as e:
        LOGGER.error(e)
        qbittorrent_client = {}
        qbittorrent_status = ""
    server_path = os.getenv("PYTHONPATH")
    content = f'''
        <div class="success-container">
            {navigation(f'{RouteHandler.LOGIN}/setup')}
            <h1>{TITLE} ⚙️ Configuration</h1>

            <div class="text-container">
                <h2>Connected Apps</h2>
                
                <div class="app-icons-container">
                    <!-- Radarr -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if radarr_status else 'red-border-shadow' }">
                            <a href="{radarr_client.Url if radarr_client and radarr_client.Url else '#'}" target="_blank" rel="noreferrer">
                                <img class="app-icon" alt="Radarr"
                                    src="https://github.com/Radarr/radarr.github.io/blob/master/logo/1024.png?raw=true"
                                    onerror="this.onerror=null; this.src='{RouteHandler.STATIC}/favicon.ico'; this.parentElement.parentElement.querySelector('.warning-badge').classList.add('visible')">
                            </a>
                            <span class="warning-badge" title="Radarr app image did not load">⚠️</span>
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
                            <a href="{sonarr_client.Url if sonarr_client and sonarr_client.Url else '#'}" target="_blank" rel="noreferrer">
                                <img class="app-icon" alt="Sonarr"
                                    src="https://github.com/Sonarr/Sonarr/blob/main/Logo/1024.png?raw=true"
                                    onerror="this.onerror=null; this.src='{RouteHandler.STATIC}/favicon.ico'; this.parentElement.parentElement.querySelector('.warning-badge').classList.add('visible')">
                            </a>
                            <span class="warning-badge" title="Sonarr app image did not load">⚠️</span>
                        </div>
                        <div class="app-info">
                            <span class="app-name">{ sonarr_client.ServerName if sonarr_client and sonarr_client.ServerName else 'Sonarr' }</span>
                            <span class="app-version">{sonarr_status['version'] if sonarr_status and 'version' in sonarr_status else '?'}</span>
                            <span class="status-dot { 'healthy' if sonarr_status else 'unhealthy' }"></span>
                        </div>
                    </div>
                    
                    <!-- qBittorrent -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if qbittorrent_status else 'red-border-shadow' }">
                            <a href="{qbittorrent_client.Url if qbittorrent_client and qbittorrent_client.Url else '#'}" target="_blank" rel="noreferrer">
                                <img class="app-icon" alt="qBittorrent"
                                    src="https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png"
                                    onerror="this.onerror=null; this.src='{RouteHandler.STATIC}/favicon.ico'; this.parentElement.parentElement.querySelector('.warning-badge').classList.add('visible')">
                            </a>
                            <span class="warning-badge" title="qBittorrent app image did not load">⚠️</span>
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

            <div class="text-container">
                <div class="key-label">📋 Interactive Setup Script for { 'PowerShell' if os.name == 'nt' else 'Shell' }</div>
                <div class="key-value">{ f'cd {'/srv/dev/yorznab' + server_path} && ./setup.ps1' if os.name == 'nt'
                                         else f'cd {'C:/Docker/yorznab' + server_path} && chmod +x setup.sh && ./setup.sh' }</div>
            </div>
            <div class="copy-actions">
                <button class="copy-btn" onclick="copyKey('setupCommand')">📋 Copy Setup Command</button>
            </div>
        </div>'''
    
    return Response(content=page_template(title="Configuration", content=content, token=token, js="cmd.js"), media_type="text/html")