import asyncio
from dataclasses import MISSING, dataclass, fields
import traceback
from typing import Callable, Dict, List, NamedTuple, Optional, Union, get_args, get_origin, get_type_hints

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.entities.YorznabClient import YorznabClient
from server.routers.handler import RouteHandler
from server.entities.BaseClient import BaseClient
from server.entities.ArrClient import ArrClient, ArrType
from server.entities.QBitClient import QBitClient
from server.entities.SeerrClient import SeerrClient
from server.web.common import LOGGER, navigation, page_template
from server.web.routers.auth import add_csrf_tokens, authenticate, gen_csrf_token
        
def build_input_template(csrf_token: str, client: Optional[BaseClient] = None, config: Optional[dataclass] = None) -> str:
    def get_input_type(field_type) -> str:
        type_map = {
            int: 'type="number" step="1"',
            float: 'type="number"',
            bool: 'type="checkbox"',
        }
        if get_origin(field_type) is Union:
            for t in get_args(field_type):
                if t in type_map:
                    return type_map[t]
        return type_map.get(field_type, 'type="text"')

    if client is not None:
        config = client.Config
        setting_name = client.ServerConfigHtml
        placeholder_url = client.DefaultUrl
    elif config is not None:
        setting_name = config.__class__.__name__
        placeholder_url = config.Url if hasattr(config, 'Url') else ''
    else:
        raise ValueError("Client must be provided to build HTML input.")
    html_input = ''
    html_input += f'''
        <template id="template-{setting_name}">
        <form class="app-settings-form" method="post" action="{RouteHandler.SETTINGS}/save?config={setting_name}" data-csrf="{csrf_token}">
        <input type="hidden" name="csrf_token" value="{csrf_token}">
        <h2>{setting_name} Settings</h2>'''
    type_hints = get_type_hints(type(config))
    for field in fields(config):
        value = getattr(config, field.name)
        placeholder = ((
            placeholder_url if field.name == "Url"
            else field.default_factory() if field.default_factory is not MISSING
            else field.default if field.default is not MISSING
            else ''
        ))
        metadata = field.metadata if field.metadata != MISSING else {}
        hint = metadata.get("description", "")
        required_input = ' required' if metadata.get("required", False) else ''
        hidden_input = ' style="display: none;"' if metadata.get("hidden", False) else ''
        display_name = metadata.get("name", "") or field.name
        is_password = metadata.get("password", False)
        constraints = ' min="' + str(metadata.get("min", "")) + '" max="' + str(metadata.get("max", "")) + '"'
        input_type = (
            'type="password" autocomplete="off" data-type="password"' if is_password
            else get_input_type(type_hints[field.name]) + constraints
        )

        html_input += f'''
            <div {hidden_input}>
            <div class="info-hint" title="{hint}">
            <div class="info-item">'''
        html_input += f'''
            <span class="info-label">
                <label for="field-{setting_name}-{field.name}">{display_name}</label>
            </span>
            <span class="info-value">'''
        html_input += f'''
            <div class="password-wrapper">''' if is_password else ''
        html_input += f'''
            <input {input_type} value="{value}" id="field-{setting_name}-{field.name}" name="{field.name}" placeholder="{placeholder}" {required_input}>'''
        html_input += f'''
            <button type="button" class="toggle-btn" id="toggleBtn-{setting_name}-{field.name}" aria-label="Toggle password visibility">
                <span class="eye-icon">👁️</span>
            </button></div>''' if is_password else ''
        html_input += f'''
            </span>''' # Info value
        html_input += f'''
            </div>
            <div class="hint-message">{hint}</div>
            </div>''' # Info item
        html_input += f'''
            </div>''' # Hidden div
    html_input += f'''
            <br>
            <button type="submit" class="app-save-btn" data-error="error-{setting_name}">💾 Save {setting_name} Settings</button>
            <p id="error-{setting_name}" class="error-message" style="display: none;">{display_name}: Unknown error occurred</p>
        </form>
        </template>''' # Container
    return html_input

router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"], include_in_schema=False)

@router.get("/applications")
async def applications_page(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)

    class ClientResult(NamedTuple):
        client: BaseClient
        status: str
        html_app: str
        input_template: str
        csrf_token: str
        exceptions: List[str]
    
    async def init_app(name: str, fn_client: Callable[..., BaseClient], icon_url: str, path_url: str = '') -> ClientResult:
        # Build app items html
        def build_html_app(name: str, status: str, client_url: str, icon_url: str, path_url: str = '') -> str:
            placeholder_image = f' style="background-image: url(\'{RouteHandler.get_static_url("favicon.ico")}\')"' if client_url else ''
            return f'''<!-- {name} -->
                <div class="app-item">
                    <div class="icon-wrapper { 'green-border-shadow' if status else 'red-border-shadow' }"{placeholder_image} onclick="toggleSettings('template-{name}')">
                        <img class="app-icon" alt="{name}"
                            src="{icon_url}"
                            onerror="this.onerror=null; this.parentElement.querySelector('.warning-badge').classList.add('visible')"
                            onload="this.classList.add('loaded'); this.parentElement.style.backgroundImage = 'none';">
                        <span class="warning-badge" title="{name} app image did not load">⚠️</span>
                    </div>
                    <div class="app-info">
                        <a href="{client_url + path_url if client_url else '#'}" target="_blank" rel="noreferrer">
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
        input_template = None
        exceptions = []
        csrf_token = None
        try:
            client = fn_client()
            csrf_token = gen_csrf_token()
            input_template = build_input_template(csrf_token=csrf_token, client=client)
            status = await client.Version
            LOGGER.debug(f"{name} Status: {status}")
        except Exception as e:
            exceptions.append(f"{name}: {e}")
            LOGGER.warning(traceback.format_exc())
            LOGGER.warning(f"Error occurred while initializing {name}: {e}")
            
        if client is not None and client.ServerNameHtml:
            name = client.ServerNameHtml
        client_url = client.Url if client and client.Url else None
        html_app = build_html_app(name=name, status=status, client_url=client_url, path_url=path_url, icon_url=icon_url)

        return ClientResult(
            client=client,
            status=status,
            html_app=html_app,
            input_template=input_template,
            csrf_token=csrf_token,
            exceptions=exceptions
        )
    
    # Create tasks with names
    tasks = [
        asyncio.create_task(
            init_app(name='Radarr', fn_client=lambda: ArrClient(ArrType.Radarr), icon_url='https://avatars.githubusercontent.com/u/25025331', path_url='/settings/indexers'),
            name='Radarr'
        ),
        asyncio.create_task(
            init_app(name='Sonarr', fn_client=lambda: ArrClient(ArrType.Sonarr), icon_url='https://avatars.githubusercontent.com/u/1082903', path_url='/settings/indexers'),
            name='Sonarr'
        ),
        asyncio.create_task(
            init_app(name='Seerr', fn_client=lambda: SeerrClient(), icon_url='https://avatars.githubusercontent.com/u/101442446', path_url='/settings/notifications/webhook'),
            name='Seerr'
        ),
        asyncio.create_task(
            init_app(name='qBittorrent', fn_client=lambda: QBitClient(), icon_url='https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png'),
            name='qBittorrent'
        ),
    ]    
    # Wait for all
    await asyncio.gather(*tasks, return_exceptions=False)
    
    # Build dict using the task's name attribute
    clients = {}
    for task in tasks:
        name = task.get_name()  # Get the name we set in create_task
        clients[name] = task.result()

    app_csrf_tokens = []
    input_templates = ""
    html_exceptions = ""
    # Format exceptions, if something is wrong with no exceptions, show a generic error message
    for name, client_result in clients.items():
        if client_result.csrf_token:
            app_csrf_tokens.append(client_result.csrf_token)
        if client_result.input_template:
            input_templates += client_result.input_template
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
            <h1>{YorznabClient().ServerNameHtml} 📲 Applications</h1>

            {input_templates}
            <div id="settings" class="text-container" style="display: none;"></div>

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
    add_csrf_tokens(request, app_csrf_tokens)
    return response
