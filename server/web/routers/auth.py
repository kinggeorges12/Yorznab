import base64
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import secrets
from fastapi import APIRouter, Form, HTTPException, Header, Query, Request, status
from fastapi.responses import JSONResponse, Response, RedirectResponse
from urllib.parse import parse_qs

# Import modules
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, TITLE, ID_NAME, navigation, page_template

dashboard_router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["auth"])

# Constants
SESSION_MAX_AGE = int(timedelta(hours=24).total_seconds())
CSRF_MAX_AGE = int(timedelta(hours=1).total_seconds())
MAX_CSRF_TOKENS = 9999  # Max tokens to store per session
CSRF_TOKEN_SIZE = 32  # Size of the CSRF token in bytes

# Helpers
def validate_passkey(passkey: str) -> bool:
    try:
        return passkey and passkey == KeyStore.get_key(ID_NAME)
    except RuntimeError:
        return False
    
def authenticate(request: Request) -> bool:
    try:
        session_token = request.cookies.get("session")
        if not session_token:
            return False
        
        payload_b64, signature = session_token.split(".")
        
        expected = hmac.new(
            KeyStore.get_key(ID_NAME).encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if signature != expected:
            return False
        
        json_str = base64.b64decode(payload_b64).decode()
        payload = json.loads(json_str)
        
        if payload["expires_at"] < datetime.now().timestamp():
            return False
        
        return True
        
    except Exception:
        return False

def set_auth_cookies(response: RedirectResponse, passkey: str, request: Request = None):
    payload = {
        "user_id": passkey,
        "issued_at": int(datetime.now().timestamp()),
        "expires_at": int(datetime.now().timestamp()) + SESSION_MAX_AGE
    }
    
    json_str = json.dumps(payload)
    payload_b64 = base64.b64encode(json_str.encode()).decode()
    
    signature = hmac.new(
        KeyStore.get_key(ID_NAME).encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()
    
    session_token = f"{payload_b64}.{signature}"
    
    is_secure = False
    if request:
        is_https = request.headers.get("x-forwarded-proto", "").lower() == "https" or request.url.scheme == "https"
        is_secure = is_https
    
    response.set_cookie("session", session_token, httponly=True, secure=is_secure, samesite="lax", max_age=SESSION_MAX_AGE)

def gen_csrf_token() -> str:
    """Generate a new CSRF token."""
    return secrets.token_hex(CSRF_TOKEN_SIZE)

def get_csrf_tokens(request: Request) -> list:
    """Get the list of valid CSRF tokens from cookie."""
    tokens_json = request.cookies.get('csrf_tokens', '[]')
    try:
        return json.loads(tokens_json)
    except json.JSONDecodeError:
        return []

def set_csrf_tokens(request: Request, response: Response, tokens: list):
    """Store the list of CSRF tokens in a cookie."""
    is_secure = False
    if request:
        is_https = request.headers.get("x-forwarded-proto", "").lower() == "https" or request.url.scheme == "https"
        is_secure = is_https
    
    # Limit token count to prevent cookie bloat
    if len(tokens) > MAX_CSRF_TOKENS:
        tokens = tokens[-MAX_CSRF_TOKENS:]
    
    response.set_cookie(
        "csrf_tokens", 
        json.dumps(tokens), 
        httponly=True, 
        secure=is_secure, 
        samesite="lax", 
        max_age=CSRF_MAX_AGE
    )

def add_csrf_token(request: Request, response: Response, csrf_token: str):
    """Add a new CSRF token to the session's token list."""
    tokens = get_csrf_tokens(request)
    if csrf_token not in tokens:
        tokens.append(csrf_token)
    set_csrf_tokens(request, response, tokens)

def validate_csrf(request: Request, csrf_token_form: str) -> bool:
    """Validate CSRF token against the list of valid tokens."""
    if not csrf_token_form:
        return False
    
    tokens = get_csrf_tokens(request)
    return csrf_token_form in tokens

def consume_csrf_token(request: Request, response: Response, csrf_token_form: str) -> bool:
    """Validate and remove a CSRF token (single-use)."""
    if not csrf_token_form:
        return False
    
    tokens = get_csrf_tokens(request)
    if csrf_token_form in tokens:
        tokens.remove(csrf_token_form)
        set_csrf_tokens(request, response, tokens)
        return True
    return False

# Routes
@dashboard_router.get(f"/", include_in_schema=False)
async def login_page(request: Request):
    # Generate CSRF token
    csrf_token = gen_csrf_token()

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
        <div class="error-container" style="display: none;">
            <p class="error-message">You provided an invalid Login Passkey.</p>
            <p class="hint-message">Recover your credentials ({ID_NAME}) from the <file>app/config/keys.yaml</file> file.</p>
        </div>'''
    
    content = f'''
        <div class="login-container">
            {navigation('')}
            <h1>Welcome to {TITLE}</h1>
            {get_started}
            <form id="loginForm" autocomplete="off" method="POST" action="{RouteHandler.AUTH}/login">
                <input type="hidden" name="csrf_token" value="{csrf_token}">
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
    
    response = Response(content=page_template(title="Login", content=content, token=csrf_token, js="js/auth.js"), status_code=status.HTTP_200_OK, media_type="text/html")
    add_csrf_token(request, response, csrf_token)
    return response


router = APIRouter(prefix=RouteHandler.AUTH, tags=["auth"])

@router.post(f"/login")
async def login_submit(
    request: Request,
    passkey: str = Form(...),
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token
    
    # Validate CSRF token against the list
    if not validate_csrf(request, csrf_token_form):
        LOGGER.warning(f"CSRF validation failed")
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "success": False,
                "error": "CSRF validation failed. Please refresh and try again.",
                "code": "CSRF_INVALID"
            }
        )
    
    # Handle first-time setup
    if not KeyStore.is_ready():
        LOGGER.debug(f"Writing keys to file. passkey: {passkey[:3]}...")
        KeyStore.write_keys(passkey)
    
    # Validate passkey
    if not validate_passkey(passkey):
        LOGGER.error(f"User authentication failed - invalid passkey")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "success": False,
                "error": "Invalid Login Passkey. Please try again.",
                "code": "AUTH_FAILED"
            }
        )
    
    # Authentication successful
    LOGGER.debug(f"User authenticated successfully")
    
    # Create response with cookies
    response = JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "message": "Login successful",
            "redirect": f"{RouteHandler.DASHBOARD}/home"
        }
    )
    
    # Set auth cookies
    set_auth_cookies(response, passkey, request)
    
    # Clear all CSRF tokens after successful login
    set_csrf_tokens(request, response, [])
    
    return response


@router.post(f"/logout")
async def logout(request: Request,
                 x_csrf_token: str = Header(None, alias="X-CSRF-Token")):
    body = await request.body()
    parsed = parse_qs(body.decode('utf-8'))
    csrf_token_form = x_csrf_token or parsed.get('csrf_token', [''])[0]
    
    response = RedirectResponse(url=f"{RouteHandler.DASHBOARD}/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Validate and consume CSRF token
    if consume_csrf_token(request, response, csrf_token_form):
        LOGGER.debug("User logged out with valid CSRF")
    else:
        LOGGER.error("Logout CSRF validation failed")
        return RedirectResponse(url=f"{RouteHandler.DASHBOARD}/", status_code=status.HTTP_303_SEE_OTHER)
    
    # Always logout regardless of CSRF (but CSRF protects against forged requests)
    response.delete_cookie("session")
    set_csrf_tokens(request, response, [])  # Clear all CSRF tokens
    
    return response