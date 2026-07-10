from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import TITLE, get_csrf_token, navigation, page_template
from server.web.routers.auth import authenticate, logout

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/keys")
async def keys(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    
    token = get_csrf_token()
    api_key = KeyStore.get_key('API_KEY')
    webhook_key = KeyStore.get_key('WEBHOOK_KEY')
    
    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.LOGIN}/keys')}
            <h1>{TITLE} 🔐 Credentials</h1>
            <div class="text-container">
                <div class="key-label">🔑 API Key for Radarr &amp; Sonarr</div>
                <div class="key-value" id="apiKey">{api_key}</div>
            </div>
            <div class="text-container">
                <div class="key-label">🔗 Webhook Key for Jellyseerr</div>
                <div class="key-value" id="webhookKey">{webhook_key}</div>
            </div>
            <div class="copy-actions">
                <button class="copy-btn" onclick="copyKey('apiKey')">🔑 Copy API Key</button>
                <button class="copy-btn" onclick="copyKey('webhookKey')">🔗 Copy Webhook Key</button>
            </div>
            <div>
                <button id="resetBtn" class="reset-btn" data-reset="{RouteHandler.LOGIN}/reset" onclick="confirmReset()">
                    🔄 Reset All Keys
                </button>
            </div>
        </div>'''
    
    return Response(content=page_template(title="Credentials", content=content, token=token, js="credentials.js", css="credentials.css"), media_type="text/html")

@router.post("/reset")
async def reset_config(request: Request):
    """Reset configuration to default state"""
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    try:
        body = await request.json()
        if not body.get('confirm'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Confirmation required")
        KeyStore.reset_keys()
        return await logout()
    
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Reset failed: {str(e)}")
