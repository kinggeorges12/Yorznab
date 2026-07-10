import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from fastapi import APIRouter, Query, Request, status
from fastapi.responses import Response, RedirectResponse
from urllib.parse import parse_qs

# Import modules
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, TITLE, ID_NAME, get_csrf_token, navigation, page_template

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

# Helpers
def validate_passkey(passkey: str) -> bool:
    try:
        return passkey and passkey == KeyStore.get_key(ID_NAME)
    except RuntimeError:
        return False
    
def authenticate(request: Request) -> bool:
    """Verify token from request cookies and return True if valid"""
    try:
        # Get the session token from cookies
        session_token = request.cookies.get("session")
        
        if not session_token:
            return False
        
        payload_b64, signature = session_token.split(".")
        
        # Check signature matches
        expected = hmac.new(
            KeyStore.get_key(ID_NAME).encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected:
            return False
        
        # Decode payload
        json_str = base64.b64decode(payload_b64).decode()
        payload = json.loads(json_str)
        
        # Check expiration
        if payload["expires_at"] < datetime.now().timestamp():
            return False
        
        return True
        
    except Exception as e:
        return False


def set_auth_cookies(response: RedirectResponse, passkey: str, request: Request = None):
    max_age = int(timedelta(hours=24).total_seconds())

    payload = {
        "user_id": passkey,
        "issued_at": int(datetime.now().timestamp()),
        "expires_at": int(datetime.now().timestamp()) + max_age
    }
    
    # Convert to JSON and base64
    json_str = json.dumps(payload)
    payload_b64 = base64.b64encode(json_str.encode()).decode()
    
    # Sign it
    signature = hmac.new(
        KeyStore.get_key(ID_NAME).encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()
    
    session_token = f"{payload_b64}.{signature}"
    
    # Determine if we should use secure flag
    is_secure = False  # Default to False for all connections
    
    # Optionally, you can check if it's HTTPS
    if request:
        is_https = request.headers.get("x-forwarded-proto", "").lower() == "https" or request.url.scheme == "https"
        is_secure = is_https  # Only set secure=True for HTTPS
    
    response.set_cookie("session", session_token, httponly=True, secure=is_secure, samesite="lax", max_age=max_age)
    response.set_cookie("passkey", passkey, httponly=True, secure=is_secure, samesite="lax", max_age=max_age)


# Routes
@router.get('')
async def login_page(request: Request, passkey: str = Query(None), failed: bool = Query(False)):
    
    token = get_csrf_token()

    if validate_passkey(passkey):
        response = RedirectResponse(url=f"{RouteHandler.LOGIN}/home", status_code=status.HTTP_303_SEE_OTHER)
        set_auth_cookies(response, passkey, request)
        return response
    
    first_time = not KeyStore.is_ready()

    temp_passkey = KeyStore.get_key(ID_NAME) if first_time else ''

    get_started = f'''
                <p>It looks like you're new here. Let's get started!</p>
                <br>
                <label for="{ID_NAME}">Enter a new Login Passkey or use the default randomized key:</label>''' if first_time else f'''
                <label for="{ID_NAME}">Please enter your Login Passkey to login to the dashboard:</label>'''

    login_button = f'''
                <button type="submit">💾 Save Login Passkey</button>
                <p class="hint-message">You can save this login passkey in your browser's keychain after clicking this button.</p>
                ''' if first_time else f'''
                <button type="submit">👤 Login</button>'''

    error = f'''
        <div class="error-container">
            <p class="error-message">You provided an invalid Login Passkey.</p>
            <p class="hint-message">Recover your credentials ({ID_NAME}) from the <file>app/config/keys.yaml</file> file.</p>
        </div>''' if failed else ""
    
    content = f'''
        <div class="login-container">
            {navigation('')}
            <h1>Welcome to {TITLE}</h1>
            {get_started}
            <form id = "loginForm" autocomplete="off" method="POST" action="{RouteHandler.LOGIN}">
                <input type="hidden" name="csrf_token" value="{token}">
                <div class="form-group">
                    <input type="text" value="yorznab" autocomplete="off" name="username" style="display:none">
                    <div class="password-wrapper">
                        <input type="password" value="{temp_passkey}" autocomplete="off" id="{ID_NAME}" name="passkey" placeholder="{ID_NAME}" required>
                        <button type="button" class="toggle-btn" {"onload" if first_time else ""} id="toggleBtn" aria-label="Toggle password visibility">
                            <span class="eye-icon">👁️</span>
                        </button>
                    </div>
                </div>
                {login_button}
            </form>
            {error}
        </div>'''
    
    return Response(content=page_template(title="Login", content=content, token=token), status_code=200, media_type="text/html")


@router.post('')
async def login_submit(request: Request):
    body = await request.body()
    parsed = parse_qs(body.decode('utf-8'))
    passkey = parsed.get('passkey', [''])[0]
    csrf_token = parsed.get('csrf_token', [''])[0]
    
    if not csrf_token or len(csrf_token) != 32:
        return RedirectResponse(url=f"{RouteHandler.LOGIN}?failed=true", status_code=status.HTTP_303_SEE_OTHER)

    if not KeyStore.is_ready():
        LOGGER.debug(f"Writing keys to file. passkey: {passkey}, CSRF Token: {csrf_token}")
        KeyStore.write_keys(passkey)
    
    if validate_passkey(passkey):
        LOGGER.debug(f"User authenticated. CSRF Token: {csrf_token}")
        response = RedirectResponse(url=f"{RouteHandler.LOGIN}/home", status_code=status.HTTP_303_SEE_OTHER)
        set_auth_cookies(response, passkey, request)
        return response
    
    LOGGER.error(f"User authentication failed. Passkey: {passkey}, CSRF Token: {csrf_token}")
    return RedirectResponse(url=f"{RouteHandler.LOGIN}?failed=true", status_code=status.HTTP_303_SEE_OTHER)



@router.post(f"/logout")
async def logout():
    response = RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session")
    response.delete_cookie("passkey")
    LOGGER.debug(f"User logged out, cookies cleared.")
    return response