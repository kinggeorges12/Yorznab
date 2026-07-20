from fastapi import APIRouter, HTTPException, Header, Request, Response, requests, status
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, TITLE, navigation, page_template
from server.web.routers.auth import authenticate, logout, validate_csrf, add_csrf_token, gen_csrf_token

router = APIRouter(prefix=RouteHandler.DASHBOARD)

@router.get("/keys", include_in_schema=False)
async def keys(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)
    
    csrf_token = gen_csrf_token()
    indexer_key = KeyStore.get_key('INDEXER_KEY')
    webhook_key = KeyStore.get_key('WEBHOOK_KEY')
    
    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/keys')}
            <h1>{TITLE} 🔐 Credentials</h1>
            <div class="text-container">
                <div class="key-label">🔑 Indexer Key for Radarr &amp; Sonarr</div>
                <div class="key-value" id="apiKey">{indexer_key}</div>
                <br>
                <p class="hint-message">
                    Check out the GitHub page to learn how to setup an Indexer:
                    <a href="https://github.com/kinggeorges12/Yorznab#indexer" target="_blank" rel="noopener noreferrer">
                        <span>https://github.com/kinggeorges12/Yorznab#indexer</span>
                    </a>
                </p>
            </div>
            <div class="text-container">
                <div class="key-label">🪝 Webhook Key for Jellyseerr</div>
                <div class="key-value" id="webhookKey">{webhook_key}</div>
                <br>
                <p class="hint-message">
                    Check out the GitHub page to learn how to setup a Webhook:
                    <a href="https://github.com/kinggeorges12/Yorznab#webhook" target="_blank" rel="noopener noreferrer">
                        <span>https://github.com/kinggeorges12/Yorznab#webhook</span>
                    </a>
                </p>
            </div>
            <div class="copy-actions">
                <button type="button" class="copy-btn" onclick="copyKey('apiKey')">🔑 Copy Indexer Key</button>
                <button type="button" class="copy-btn" onclick="copyKey('webhookKey')">🪝 Copy Webhook Key</button>
            </div>
            <div>
                <button id="resetBtn" class="reset-btn" data-reset="{RouteHandler.AUTH}/reset" data-csrf="{csrf_token}" onclick="confirmReset()">
                    🔄 Reset All Keys
                </button>
            </div>
        </div>'''
    
    
    response = Response(content=page_template(title="Credentials", content=content, js="js/credentials.js", css="css/credentials.css"), media_type="text/html")
    add_csrf_token(request, response, csrf_token)
    return response

@router.post(f"{RouteHandler.AUTH}/reset", tags=["auth"])
async def reset_config(request: Request,
                       x_csrf_token: str = Header(..., alias="X-CSRF-Token")):
    """Reset configuration to default state"""
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    try:
        # Get CSRF token from header (since this is a JSON API)
        csrf_token_header = x_csrf_token

        body = await request.json()
        
        # Validate CSRF token
        if not validate_csrf(request, csrf_token_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
        
        if not body.get('confirm'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation required")
        
        KeyStore.reset_keys()
        
        # Create response and consume CSRF token
        response = await logout(request)
        return response
    
    except Exception as e:
        LOGGER.error(f"Reset failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Reset failed")
    