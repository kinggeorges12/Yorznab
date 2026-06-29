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
    exceptions = []

    try:
        radarr_client = ArrClient(ArrType.Radarr)
        radarr_status = radarr_client.status() if radarr_client else ""
        LOGGER.debug(f"Radarr Status: {radarr_status}")
    except Exception as e:
        exceptions.append(f"Radarr: {e}")
        radarr_client = {}
        radarr_status = ""
    try:
        sonarr_client = ArrClient(ArrType.Sonarr)
        sonarr_status = sonarr_client.status() if sonarr_client else ""
        LOGGER.debug(f"Sonarr Status: {sonarr_status}")
    except Exception as e:
        exceptions.append(f"Sonarr: {e}")
        sonarr_client = {}
        sonarr_status = ""
    try:
        qbittorrent_client = QBitClient()
        qbittorrent_status = qbittorrent_client.version() if qbittorrent_client else ""
        LOGGER.debug(f"qBittorrent Status: {qbittorrent_status}")
    except Exception as e:
        exceptions.append(f"qBittorrent: {e}")
        qbittorrent_client = {}
        qbittorrent_status = ""

    # Format exceptions, if something is wrong with no exceptions, show a generic error message
    html_exceptions = '<p class="error-message">Radarr: Unknown error occurred</p>' if not exceptions and not radarr_status else ""
    html_exceptions = '<p class="error-message">Sonarr: Unknown error occurred</p>' if not exceptions and not sonarr_status else ""
    html_exceptions = '<p class="error-message">qBittorrent: Unknown error occurred</p>' if not exceptions and not qbittorrent_status else ""
    for e in exceptions:
        html_exceptions += f'<p class="error-message">{e}</p>\n'

    # Build app items html
    def build_apps_html(name: str, url: str, status: str, icon_url: str) -> str:
        return f'''<!-- {name} -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if status else 'red-border-shadow' }" {
                            f'''style="background-image: url('{RouteHandler.STATIC}/favicon.ico')"''' if url else ''}>
                            <a href="{url if url else '#'}" target="_blank" rel="noreferrer">
                                <img class="app-icon" alt="{name}"
                                    src="{icon_url}"
                                    onerror="this.onerror=null; this.parentElement.parentElement.querySelector('.warning-badge').classList.add('visible')"
                                    onload="this.classList.add('loaded'); this.parentElement.parentElement.style.backgroundImage = 'none';">
                            </a>
                            <span class="warning-badge" title="{name} app image did not load">⚠️</span>
                        </div>
                        <div class="app-info">
                            <span class="app-name">{name}</span>
                            <span class="app-version">{status if status else '?'}</span>
                            <span class="status-dot { 'healthy' if status else 'unhealthy' }"></span>
                        </div>
                    </div>'''
    
    html_apps = ''
    html_apps += build_apps_html(name = radarr_client.ServerName if radarr_client and radarr_client.ServerName else 'Radarr',
                                url = radarr_client.Url if radarr_client and hasattr(radarr_client, 'Url') and radarr_client.Url else None,
                                status = radarr_status['version'] if radarr_status and 'version' in radarr_status else None,
                                icon_url = 'https://github.com/Radarr/radarr.github.io/blob/master/logo/1024.png?raw=true')
    html_apps += build_apps_html(name = sonarr_client.ServerName if sonarr_client and sonarr_client.ServerName else 'Sonarr',
                                url = sonarr_client.Url if sonarr_client and hasattr(sonarr_client, 'Url') and sonarr_client.Url else None,
                                status = sonarr_status['version'] if sonarr_status and 'version' in sonarr_status else None,
                                icon_url = 'https://github.com/Sonarr/Sonarr/blob/main/Logo/1024.png?raw=true')
    html_apps += build_apps_html(name = qbittorrent_client.ServerName if qbittorrent_client and qbittorrent_client.ServerName else 'qBittorrent',
                                url = qbittorrent_client.Url if qbittorrent_client and hasattr(qbittorrent_client, 'Url') and qbittorrent_client.Url else None,
                                status = qbittorrent_status or None,
                                icon_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png')

    # Get path for config instructions
    server_path = os.getenv("PYTHONPATH")

    content = f'''
        <div class="success-container">
            {navigation(f'{RouteHandler.LOGIN}/setup')}
            <h1>{TITLE} ⚙️ Configuration</h1>

            <div class="text-container">
                <h2>Connected Apps</h2>
                
                <div class="app-icons-container">
                    {html_apps}
                </div>
            </div>
            
            <div class="error-container" style="display: {'flex' if not radarr_status or not sonarr_status or not qbittorrent_status else 'none'};">
                {html_exceptions}
                <p class="hint-message">Please login to your server and run the setup script from the command line.</p>
            </div>

            <div class="text-container">
                <div class="key-label">📋 Interactive Setup Script for { 'PowerShell' if os.name == 'nt' else 'Shell' }</div>
                <div class="key-value">{ f'cd C:/Docker/yorznab{server_path} && ./setup.ps1' if os.name == 'nt'
                                         else f'cd /srv/dev/yorznab{server_path} && chmod +x setup.sh && ./setup.sh' }</div>
            </div>
            <div class="copy-actions">
                <button class="copy-btn" onclick="copyKey('setupCommand')">📋 Copy Setup Command</button>
            </div>
        </div>'''
    
    return Response(content=page_template(title="Configuration", content=content, token=token, js="cmd.js"), media_type="text/html")