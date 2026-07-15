import os
import html
from pathlib import Path
from fastapi import APIRouter, Request, Response, WebSocket, status
from fastapi.responses import RedirectResponse

# Import modules
from server.web.websocket.factory import WebSetup
from server.routers.handler import RouteHandler
from server.rss.ArrClient import ArrClient, ArrType
from server.rss.QBitClient import QBitClient
from server.web.common import LOGGER, TITLE, get_csrf_token, navigation, page_template
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/setup")
async def setup(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)

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
        qbittorrent_status = qbittorrent_client.status() if qbittorrent_client else ""
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
        placeholder_image = f'style="background-image: url(\'{RouteHandler.STATIC}/favicon.ico\')"' if url else ''
        return f'''<!-- {name} -->
                    <div class="app-item">
                        <div class="icon-wrapper { 'green-border-shadow' if status else 'red-border-shadow' }"{placeholder_image}>
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
                                icon_url = 'https://avatars.githubusercontent.com/u/25025331')
    html_apps += build_apps_html(name = sonarr_client.ServerName if sonarr_client and sonarr_client.ServerName else 'Sonarr',
                                url = sonarr_client.Url if sonarr_client and hasattr(sonarr_client, 'Url') and sonarr_client.Url else None,
                                status = sonarr_status['version'] if sonarr_status and 'version' in sonarr_status else None,
                                icon_url = 'https://avatars.githubusercontent.com/u/1082903')
    html_apps += build_apps_html(name = qbittorrent_client.ServerName if qbittorrent_client and qbittorrent_client.ServerName else 'qBittorrent',
                                url = qbittorrent_client.Url if qbittorrent_client and hasattr(qbittorrent_client, 'Url') and qbittorrent_client.Url else None,
                                status = qbittorrent_status or None,
                                icon_url = 'https://upload.wikimedia.org/wikipedia/commons/thumb/6/66/New_qBittorrent_Logo.svg/1280px-New_qBittorrent_Logo.svg.png')

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.LOGIN}/setup')}
            <h1>{TITLE} ⚙️ Configuration</h1>

            <div id="appIconsContainer" class="text-container">
                <h2>Connected Apps</h2>
                
                <div class="app-icons-container">
                    {html_apps}
                </div>
                <div class="error-container" style="display: {'flex' if not radarr_status or not sonarr_status or not qbittorrent_status else 'none'};">
                    {html_exceptions}
                <p class="hint-message">Try the <a href="#" onclick="showTerminal()">🖥️ Interactive Setup</a> to configure your apps.</p>
            </div>

            </div>
            
            <div class="terminal-container" id="terminalConfig" data-ws="{RouteHandler.LOGIN}/setup/ws">
                <div class="terminal-header">
                    <span class="terminal-title">🖥️ Interactive Setup: {WebSetup.shell_name()}</span>
                    <div class="terminal-controls">
                        <span class="terminal-dot red"></span>
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-dot green"></span>
                    </div>
                </div>
                <div class="terminal-output" id="terminalOutput">
                    <div class="terminal-line system">⏳ Initializing setup environment...</div>
                    <div class="terminal-line system">📌 Running:<br>{'<br>'.join(WebSetup.commands())}</div>
                    <div class="terminal-line system">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
                </div>
                <div class="terminal-input-container">
                    <span class="prompt-symbol">{WebSetup.prompt()}</span>
                    <input type="text" id="terminalInput" class="terminal-input" placeholder="Type your response here..." />
                    <button type="button" id="sendBtn" class="term-btn term-btn-primary">Send</button>
                </div>
                <div class="terminal-footer">
                    <div class="terminal-status" id="terminalStatus">
                        <span class="status-indicator error"></span>
                        <span id="statusText">Loading</span>
                    </div>
                    <button type="button" id="runSetupBtn" class="term-btn term-btn-primary">▶️ Run Setup</button>
                    <div class="terminal-actions">
                        <button type="button" id="clearBtn" class="term-btn term-btn-secondary" onclick="clearTerminal()">🗑️ Clear</button>
                        <button type="button" id="copyBtn" class="term-btn term-btn-secondary" onclick="copyTerminalOutput()">📋 Copy</button>
                    </div>
                </div>
            </div>
            <div class="button-container">
                <button type="button" class="nav-toggle-button active" data-container="appIconsContainer">📱 Connected Apps</button>
                <button type="button" class="nav-toggle-button" data-container="terminalConfig">🖥️ Interactive Setup</button>
            </div>
        </div>'''
    
    return Response(content=page_template(title="Configuration", content=content, token=token, js="js/terminal.js", css=["css/setup.css", "cache/css/dejavu-sans-mono"]), media_type="text/html")

@router.websocket("/setup/ws")
async def websocket_setup(websocket: WebSocket):
    """WebSocket endpoint to run a script with interactive terminal"""
    # Run WebSetup handler
    WEB_SETUP = WebSetup()
    await WEB_SETUP.run(websocket)
