from datetime import timedelta
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response, RedirectResponse
from urllib.parse import parse_qs

# Import modules
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, TITLE, ID_NAME, authenticated, get_csrf_token, page_template

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

# Helpers
def validate_appid(appid: str) -> bool:
    return appid and appid == KeyStore.get_key(ID_NAME)

def set_auth_cookies(response: RedirectResponse, appid: str, request: Request = None):
    max_age = int(timedelta(hours=24).total_seconds())
    
    # Determine if we should use secure flag
    is_secure = False  # Default to False for all connections
    
    # Optionally, you can check if it's HTTPS
    if request:
        is_https = request.headers.get("x-forwarded-proto", "").lower() == "https" or request.url.scheme == "https"
        is_secure = is_https  # Only set secure=True for HTTPS
    
    response.set_cookie("authenticated", "true", httponly=True, secure=is_secure, samesite="lax", max_age=max_age)
    response.set_cookie("appid", appid, httponly=True, secure=is_secure, samesite="lax", max_age=max_age)


# Routes
@router.get('')
async def login_page(request: Request, appid: str = Query(None), failed: bool = Query(False)):
    if authenticated(request):
        return RedirectResponse(url=f"{RouteHandler.LOGIN}/success", status_code=303)
    
    if validate_appid(appid):
        response = RedirectResponse(url=f"{RouteHandler.LOGIN}/success", status_code=303)
        set_auth_cookies(response, appid, request)
        return response
    
    token = get_csrf_token()
    error = f'''
<div class="error-container">
    <p class="error-message">Invalid API Key provided.</p>
    <p class="hint-message">Did you try setting the Docker environment variable "{ID_NAME}"?</p>
</div>''' if (failed or validate_appid(appid)) else ""
    
    content = f'''
        <div class="login-container">
            <h1>Welcome to {TITLE}</h1>
            <form autocomplete="off" method="POST" action="{RouteHandler.LOGIN}">
                <input type="hidden" name="csrf_token" value="{token}">
                <div class="form-group">
                    <label for="appid">Please enter your App ID to show API keys:</label>
                    <div class="password-wrapper">
                        <input type="password" autocomplete="off" id="{ID_NAME}" name="appid" placeholder="{ID_NAME}" required>
                        <button type="button" class="toggle-btn" id="toggleBtn" aria-label="Toggle password visibility">
                            <span class="eye-icon">👁️</span>
                        </button>
                    </div>
                </div>
                <button type="submit">Submit</button>
            </form>
            {error}
        </div>'''
    
    return Response(content=page_template(title="Login", content=content, token=token), status_code=200, media_type="text/html")


@router.post('')
async def login_submit(request: Request):
    body = await request.body()
    parsed = parse_qs(body.decode('utf-8'))
    appid = parsed.get('appid', [''])[0]
    csrf_token = parsed.get('csrf_token', [''])[0]
    
    if not csrf_token or len(csrf_token) != 32:
        return RedirectResponse(url=f"{RouteHandler.LOGIN}?failed=true", status_code=303)
    
    if validate_appid(appid):
        response = RedirectResponse(url=f"{RouteHandler.LOGIN}/success", status_code=303)
        set_auth_cookies(response, appid)
        LOGGER.debug(f"User authenticated. CSRF Token: {csrf_token}")
        return response
    
    LOGGER.error(f"User authentication failed. AppID: {appid}, CSRF Token: {csrf_token}")
    return RedirectResponse(url=f"{RouteHandler.LOGIN}?failed=true", status_code=303)



@router.post(f"/logout")
async def logout():
    response = RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    response.delete_cookie("authenticated")
    response.delete_cookie("appid")
    LOGGER.debug(f"User logged out, cookies cleared.")
    return response