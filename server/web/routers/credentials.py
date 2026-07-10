from fastapi import APIRouter, Response
from fastapi.params import Cookie
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import TITLE, get_csrf_token, navigation, page_template

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/keys")
async def keys(authenticated: str = Cookie(None)):
    if authenticated != "true":
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    
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
        </div>'''
    
    return Response(content=page_template(title="Credentials", content=content, token=token), media_type="text/html")
