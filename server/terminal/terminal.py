from fastapi import APIRouter, Request, Response, WebSocket, status
from fastapi.responses import RedirectResponse

# Import modules
from server.terminal.factory import WebSetup
from server.routers.handler import RouteHandler
from server.web.common import TITLE, navigation, page_template
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"], include_in_schema=False)

@router.get("/terminal")
async def setup(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/terminal')}
            <h1>{TITLE} 🖥️ Interactive Terminal</h1>
            
            <div class="terminal-container" id="terminalConfig" data-ws="{RouteHandler.DASHBOARD}/terminal/ws">
                <div class="terminal-header">
                    <span class="terminal-title">🖥️ Interactive Terminal: {WebSetup.shell_name()}</span>
                    <div class="terminal-controls">
                        <span class="terminal-dot red"></span>
                        <span class="terminal-dot yellow"></span>
                        <span class="terminal-dot green"></span>
                    </div>
                </div>
                <div class="terminal-output" id="terminalOutput">
                    <div class="terminal-line system">⏳ Initializing setup environment...</div>
                    <div class="terminal-line system">📌 Running:</div>
                    <div class="terminal-line system">{'</div><div class="terminal-line system">'.join(WebSetup.commands())}</div>
                    <div class="terminal-line system">{"━"*80}</div>
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
    
    return Response(content=page_template(title="Configuration", content=content, js="js/terminal.js", css=["css/setup.css", "cache/css/dejavu-sans-mono"]), media_type="text/html")

@router.websocket("/terminal/ws")
async def websocket_terminal(websocket: WebSocket):
    """WebSocket endpoint to run a script with interactive terminal"""
    # Run WebSetup handler
    WEB_SETUP = WebSetup()
    await WEB_SETUP.run(websocket)
