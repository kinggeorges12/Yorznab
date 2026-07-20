from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.rss.ArrClient import ArrClient, ArrType
from server.rss.QBitClient import QBitClient
from server.rss.SeerrClient import SeerrClient
from server.web.common import LOGGER, TITLE, navigation, page_template
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"], include_in_schema=False)

@router.get("/applications")
async def applications_page(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)

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
        seerr_client = SeerrClient()
        seerr_status = seerr_client.status() if seerr_client else ""
        LOGGER.debug(f"Seerr Status: {seerr_status}")
    except Exception as e:
        exceptions.append(f"Seerr: {e}")
        seerr_client = {}
        seerr_status = ""
    try:
        qbittorrent_client = QBitClient()
        qbittorrent_status = qbittorrent_client.status() if qbittorrent_client else ""
        LOGGER.debug(f"qBittorrent Status: {qbittorrent_status}")
    except Exception as e:
        exceptions.append(f"qBittorrent: {e}")
        qbittorrent_client = {}
        qbittorrent_status = ""

    # Format exceptions, if something is wrong with no exceptions, show a generic error message
    html_exceptions = '<p class="error-message">Radarr: Unknown error occurred</p>' if not exceptions and not radarr_status else ""
    html_exceptions = '<p class="error-message">Sonarr: Unknown error occurred</p>' if not exceptions and not sonarr_status else ""
    html_exceptions = '<p class="error-message">Seerr: Unknown error occurred</p>' if not exceptions and not seerr_status else ""
    html_exceptions = '<p class="error-message">qBittorrent: Unknown error occurred</p>' if not exceptions and not qbittorrent_status else ""
    for e in exceptions:
        html_exceptions += f'<p class="error-message">{e}</p>\n'

    # Build app items html
    def build_apps_html(name: str, url: str, status: str, icon_url: str) -> str:
        placeholder_image = f'style="background-image: url(\'{RouteHandler.get_static_url("favicon.ico")}\')"' if url else ''
        return f'''<!-- {name} -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if status else 'red-border-shadow' }"{placeholder_image}>
                            <img class="app-icon" alt="{name}"
                                src="{icon_url}"
                                onerror="this.onerror=null; this.parentElement.querySelector('.warning-badge').classList.add('visible')"
                                onload="this.classList.add('loaded'); this.parentElement.style.backgroundImage = 'none';">
                            <span class="warning-badge" title="{name} app image did not load">⚠️</span>
                        </div>
                        <div class="app-info">
                            <a href="{url if url else '#'}" target="_blank" rel="noreferrer">
                                <span>
                                    <span class="status-dot { 'healthy' if status else 'unhealthy' }"></span>
                                    <span class="app-name">{name}</span>
                                    <span class="app-version">{status if status else '?'}</span>
                                </span>
                            </a>
                        </div>
                    </div>'''
    
    html_apps = ''
    html_apps += '<div class="app-icons-container">'
    html_apps += build_apps_html(name = radarr_client.ServerName if radarr_client and radarr_client.ServerName else 'Radarr',
                                url = radarr_client.Url if radarr_client and hasattr(radarr_client, 'Url') and radarr_client.Url else None,
                                status = radarr_status['version'] if radarr_status and 'version' in radarr_status else None,
                                icon_url = 'https://avatars.githubusercontent.com/u/25025331')
    html_apps += build_apps_html(name = sonarr_client.ServerName if sonarr_client and sonarr_client.ServerName else 'Sonarr',
                                url = sonarr_client.Url if sonarr_client and hasattr(sonarr_client, 'Url') and sonarr_client.Url else None,
                                status = sonarr_status['version'] if sonarr_status and 'version' in sonarr_status else None,
                                icon_url = 'https://avatars.githubusercontent.com/u/1082903')
    html_apps += '</div>'
    html_apps += '<div class="app-icons-container">'
    html_apps += build_apps_html(name = seerr_client.ServerName if seerr_client and seerr_client.ServerName else 'Seerr',
                                url = seerr_client.Url if seerr_client and hasattr(seerr_client, 'Url') and seerr_client.Url else None,
                                status = seerr_status or None,
                                icon_url = 'https://avatars.githubusercontent.com/u/101442446')
    html_apps += build_apps_html(name = qbittorrent_client.ServerName if qbittorrent_client and qbittorrent_client.ServerName else 'qBittorrent',
                                url = qbittorrent_client.Url if qbittorrent_client and hasattr(qbittorrent_client, 'Url') and qbittorrent_client.Url else None,
                                status = qbittorrent_status or None,
                                icon_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png')
    html_apps += '</div>'

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/setup')}
            <h1>{TITLE} ⚙️ Configuration</h1>

            <div id="appIconsContainer" class="text-container">
                <h2>Connected Apps</h2>
                
                {html_apps}
                <div class="error-container" style="display: {'flex' if not radarr_status or not sonarr_status or not qbittorrent_status else 'none'};">
                    {html_exceptions}
                </div>
            </div>
        </div>'''
    
    return Response(content=page_template(title="Configuration", content=content, css="css/applications.css"), media_type="text/html")
