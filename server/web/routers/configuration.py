from fastapi import APIRouter, HTTPException, Header, Request, Response, requests, status
from fastapi.responses import RedirectResponse

# Import modules
from server.entities.Yorznab import YorznabConfig
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, navigation, page_template
from server.web.routers.applications import build_html_input
from server.web.routers.auth import authenticate, logout, validate_csrf, add_csrf_token, gen_csrf_token

router = APIRouter(prefix=RouteHandler.DASHBOARD)

@router.get("/configuration", include_in_schema=False)
async def configuration(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)
    
    indexer_key = KeyStore.get_key('INDEXER_KEY')
    webhook_key = KeyStore.get_key('WEBHOOK_KEY')

    config_csrf_tokens = []
    indexer_csrf_token = gen_csrf_token()
    cron_csrf_token = gen_csrf_token()
    reset_csrf_token = gen_csrf_token()
    config_csrf_tokens.extend([indexer_csrf_token, cron_csrf_token, reset_csrf_token])

    html_settings = ''
    html_settings += build_html_input(csrf_token=indexer_csrf_token, config=YorznabConfig().Indexer)
    html_settings += build_html_input(csrf_token=cron_csrf_token, config=YorznabConfig().Cron)

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/configuration')}
            <h1>{YorznabConfig().Indexer.Title} ⚙️ Configuration</h1>
            {html_settings}
            
            <div class="text-container">
                <h2 class="status-container">
                    <span class="status-dot" id="status-dot"></span>
                    Cron Status: <span id="status-label">⏳ Loading...</span>
                </h2>
                <div class="info-item">
                    <span class="info-label">
                        <label for="countdown">Refresh starts in:</label>
                    </span>
                    <span class="info-value countdown-display" id="countdown" data-status="{RouteHandler.STATUS}" title="Refresh starts in">
                        <span class="hours"></span>
                        <span class="separator">:</span>
                        <span class="minutes"></span>
                        <span class="separator">:</span>
                        <span class="seconds"></span>
                    </span>
                </div>
                <div class="info-item">
                    <span class="info-label">
                        <label for="scheduled">Scheduled:</label>
                    </span>
                    <span class="info-value" id="scheduled" title="Scheduled"></span>
                </div>
                <div class="info-item">
                    <span class="info-label">
                        <label for="server-time">Server time:</label>
                    </span>
                    <span class="info-value" id="server-time" title="Server time"></span>
                </div>
            </div>
            <div>
                <button id="resetBtn" class="reset-btn" data-reset="{RouteHandler.AUTH}/reset" data-csrf="{reset_csrf_token}" onclick="confirmReset()">
                    🔄 Reset All Keys
                </button>
            </div>
        </div>'''
    
    
    response = Response(content=page_template(title="Credentials", content=content, css=["css/applications.css", "css/configuration.css"], js=["js/credentials.js", "js/cron.js", "js/application.js"]), media_type="text/html")
    for csrf_token in config_csrf_tokens:
        add_csrf_token(request, response, csrf_token)
    return response

@router.post(f"{RouteHandler.AUTH}/reset", tags=["auth"])
async def reset_config(request: Request,
                       x_csrf_token: str = Header(..., alias="X-CSRF-Token")):
    """Reset configuration to default state"""
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Get CSRF token from header (since this is a JSON API)
    csrf_token_header = x_csrf_token
    
    # Validate CSRF token
    if not validate_csrf(request, csrf_token_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    
    try:
        body = await request.json()
        
        if not body.get('confirm'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation required")
        
        KeyStore.reset_keys()
        
        # Create response and consume CSRF token
        response = await logout(request)
        return response
    
    except Exception as e:
        LOGGER.error(f"Reset failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Reset failed")
    