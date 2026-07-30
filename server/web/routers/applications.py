from dataclasses import MISSING, dataclass, fields
from typing import Callable, Dict, List, NamedTuple, Optional

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.entities.Yorznab import YorznabConfig
from server.routers.handler import RouteHandler
from server.entities.AppClient import AppClient
from server.entities.ArrClient import ArrClient, ArrType
from server.entities.QBitClient import QBitClient
from server.entities.SeerrClient import SeerrClient
from server.web.common import LOGGER, navigation, page_template
from server.web.routers.auth import add_csrf_token, authenticate, gen_csrf_token
        
def build_html_input(csrf_token: str, client: Optional[AppClient] = None, config: Optional[dataclass] = None) -> str:
    if client is not None:
        config = client.Config
        setting_name = client.ServerName
        placeholder_url = client.DefaultUrl
    elif config is not None:
        setting_name = config.__class__.__name__
        placeholder_url = config.Url if hasattr(config, 'Url') else ''
    else:
        raise ValueError("Client must be provided to build HTML input.")
    html_input = ''
    html_input += f'''
        <div class="text-container" id="{setting_name}-settings" style="display: none;">
        <form class="settings-form" method="post" action="{RouteHandler.SETTINGS}/save?config={setting_name}" data-csrf="{csrf_token}">
        <h2>{setting_name} Settings</h2>'''
    for field in fields(config):
        if (field.name == "ServerType"):
            continue  # Skip ServerType field, it's not editable
        value = getattr(config, field.name)
        placeholder = field.default if field.default != MISSING and field.default else ''
        metadata = field.metadata if field.metadata != MISSING else {}
        hint = metadata.get("description", "")
        required_input = 'required' if metadata.get("required", False) else ''
        display_name = metadata.get("name", "") or field.name
        html_input += f'''
            <div class="info-hint" title="{hint}">
            <div class="info-item">'''
        html_input += f'''
            <span class="info-label">
                <label for="{field.name}">{display_name}</label>
            </span>
            <span class="info-value">'''
        match field.name:
            case "Url":
                html_input += f'''
                    <input type="text" value="{value}" id="{field.name}" name="{field.name}" placeholder="{placeholder_url}" {required_input}>'''
            case "UrlFrom":
                html_input += f'''
                    <input type="text" value="{value}" id="{field.name}" name="{field.name}" placeholder="{YorznabConfig().Indexer.Url}" {required_input}>'''
            case "ApiKey" | "Password":
                html_input += f'''
                    <input type="password" value="{value}" id="{field.name}" name="{field.name}" autocomplete="off" placeholder="{placeholder}" data-type="password" {required_input}>
                    <button type="button" class="toggle-btn" id="toggleBtn" aria-label="Toggle password visibility">
                        <span class="eye-icon">👁️</span>
                    </button>'''
            case _:
                html_input += f'''
                    <input type="text" value="{value}" id="{field.name}" name="{field.name}" placeholder="{placeholder}" {required_input}>'''
        html_input += f'''
            </span>''' # Info value
        html_input += f'''
            </div>
            <div class="hint-message">{hint}</div>
            </div>''' # Info item
    html_input += f'''
            <br>
            <button type="submit" class="save-btn">💾 Save {setting_name} Settings</button>
        </form>
        </div>''' # Container
    return html_input

router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"], include_in_schema=False)

@router.get("/applications")
async def applications_page(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)

    class ClientResult(NamedTuple):
        client: AppClient
        status: str
        html_app: str
        html_input: str
        csrf_token: str
        exceptions: List[str]
    
    def init_app(name: str, fn_client: Callable[..., AppClient], icon_url: str) -> ClientResult:
        # Build app items html
        def build_html_app(name: str, status: str, client_url: str, icon_url: str) -> str:
            onclick_action = f''' onclick="toggleSettings('{name}-settings')"'''
            placeholder_image = f' style="background-image: url(\'{RouteHandler.get_static_url("favicon.ico")}\')"' if client_url else ''
            return f'''<!-- {name} -->
                <div class="app-item">
                    <div class="icon-wrapper { 'green-border-shadow' if status else 'red-border-shadow' }"{placeholder_image}{onclick_action if status else ''}>
                        <img class="app-icon" alt="{name}"
                            src="{icon_url}"
                            onerror="this.onerror=null; this.parentElement.querySelector('.warning-badge').classList.add('visible')"
                            onload="this.classList.add('loaded'); this.parentElement.style.backgroundImage = 'none';">
                        <span class="warning-badge" title="{name} app image did not load">⚠️</span>
                    </div>
                    <div class="app-info">
                        <a href="{client_url if client_url else '#'}" target="_blank" rel="noreferrer">
                            <span>
                                <span class="status-dot { 'healthy' if status else 'unhealthy' }"></span>
                                <span class="app-name">{name}</span>
                                <span class="app-version">{status if status else '?'}</span>
                            </span>
                        </a>
                    </div>
                </div>'''
        
        client = None
        status = None
        html_input = None
        exceptions = []
        csrf_token = None
        try:
            client = fn_client()
            status = client.Version
            csrf_token = gen_csrf_token()
            html_input = build_html_input(csrf_token=csrf_token, client=client)
            LOGGER.debug(f"{name} Status: {status}")
        except Exception as e:
            exceptions.append(f"{name}: {e}")
            LOGGER.warning(f"Error occurred while initializing {name}: {e}")
            
        if client is not None and client.ServerName:
            name = client.ServerName
        client_url = client.Url if client and client.Url else None
        html_app = build_html_app(name=name, status=status, client_url=client_url, icon_url=icon_url)

        return ClientResult(
            client=client,
            status=status,
            html_app=html_app,
            html_input=html_input,
            csrf_token=csrf_token,
            exceptions=exceptions
        )
    
    clients: Dict[str, ClientResult] = {}
    clients['Radarr'] = init_app('Radarr', lambda: ArrClient(ArrType.Radarr), 'https://avatars.githubusercontent.com/u/25025331')
    clients['Sonarr'] = init_app('Sonarr', lambda: ArrClient(ArrType.Sonarr), 'https://avatars.githubusercontent.com/u/1082903')
    clients['Seerr'] = init_app('Seerr', lambda: SeerrClient(), 'https://avatars.githubusercontent.com/u/101442446')
    clients['qBittorrent'] = init_app('qBittorrent', lambda: QBitClient(), 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png')

    app_csrf_tokens = []
    html_inputs = ""
    html_exceptions = ""
    # Format exceptions, if something is wrong with no exceptions, show a generic error message
    for name, client_result in clients.items():
        if client_result.csrf_token:
            app_csrf_tokens.append(client_result.csrf_token)
        html_inputs += client_result.html_input
        html_exceptions += f'<p class="error-message">{name}: Unknown error occurred</p>' if not client_result.exceptions and not client_result.status else ""
        for e in client_result.exceptions:
            html_exceptions += f'<p class="error-message">{e}</p>\n'


    html_apps = ''
    html_apps += '<div class="app-icons-container">'
    html_apps += clients['Radarr'].html_app
    html_apps += clients['Sonarr'].html_app
    html_apps += '</div>'
    html_apps += '<div class="app-icons-container">'
    html_apps += clients['Seerr'].html_app
    html_apps += clients['qBittorrent'].html_app
    html_apps += '</div>'
            
    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/setup')}
            <h1>{YorznabConfig().ServerName} 📲 Applications</h1>

            {html_inputs}

            <div id="main-menu">
                <div id="appIconsContainer" class="text-container">
                    <h2>Connected Apps</h2>
                    
                    {html_apps}
                    <div class="error-container" style="display: {'flex' if html_exceptions else 'none'};">
                        {html_exceptions}
                    </div>
                </div>
            </div>
        </div>'''
    
    response = Response(content=page_template(title="Configuration", content=content, css="css/applications.css", js="js/application.js"), media_type="text/html")
    for csrf_token in app_csrf_tokens:
        add_csrf_token(request, response, csrf_token)

    return response
