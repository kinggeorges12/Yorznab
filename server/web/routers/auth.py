from datetime import datetime, timedelta
import secrets
from fastapi import APIRouter, Form, Header, Request, status
from fastapi.responses import JSONResponse, Response, RedirectResponse

# Import modules
from server.entities.YorznabClient import YorznabClient
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, navigation, page_template
from server.utils.docs import FASTAPI_USER

dashboard_router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["auth"])

# Constants
ID_NAME = "LOGIN_PASSKEY"
SESSION_MAX_AGE = int(timedelta(hours=24).total_seconds())
CSRF_MAX_AGE = int(timedelta(hours=1).total_seconds())
MAX_CSRF_TOKENS = 50
CSRF_TOKEN_SIZE = 16

def validate_passkey(passkey: str) -> bool:
    try:
        return passkey and passkey == KeyStore.get_key(ID_NAME)
    except RuntimeError:
        return False
    
def authenticate(request: Request) -> bool:
    """Check if user is authenticated via starsessions."""
    try:
        return request.session.get("is_authenticated", False)
    except Exception as e:
        LOGGER.error(f"Authentication check failed: {e}")
        return False

def gen_csrf_token() -> str:
    return secrets.token_hex(CSRF_TOKEN_SIZE)

def get_csrf_tokens(request: Request) -> list:
    try:
        return request.session.get("csrf_tokens", [])
    except Exception:
        return []

def add_csrf_tokens(request: Request, csrf_token: list[str]) -> None:
    for token in csrf_token:
        _add_csrf_token(request, token)

def update_csrf_headers(request: Request, response: Response) -> Response:
    new_csrf_token = gen_csrf_token()
    _add_csrf_token(request, new_csrf_token)
    response.headers["X-CSRF-Token"] = new_csrf_token
    return response

def _add_csrf_token(request: Request, csrf_token: str):
    try:
        tokens = request.session.get("csrf_tokens", [])
        if csrf_token not in tokens:
            tokens.append(csrf_token)
            if len(tokens) > MAX_CSRF_TOKENS:
                tokens = tokens[-MAX_CSRF_TOKENS:]
            request.session["csrf_tokens"] = tokens
            return True
    except Exception as e:
        LOGGER.error(f"Failed to add CSRF token: {e}")
    return False

def validate_csrf(request: Request, csrf_token_form: str) -> bool:
    if not csrf_token_form:
        return False
    try:
        tokens = request.session.get("csrf_tokens", [])
        return csrf_token_form in tokens
    except Exception:
        return False

def consume_csrf_token(request: Request, csrf_token_form: str) -> bool:
    if not csrf_token_form:
        return False
    try:
        tokens = request.session.get("csrf_tokens", [])
        if csrf_token_form in tokens:
            tokens.remove(csrf_token_form)
            request.session["csrf_tokens"] = tokens
            return True
    except Exception:
        pass
    return False

# Routes
@dashboard_router.get(RouteHandler.LOGIN, include_in_schema=False)
async def login_page(request: Request):
    # Session is already loaded by SessionAutoloadMiddleware
    session = request.session
    
    csrf_token = gen_csrf_token()
    tokens = session.get("csrf_tokens", [])
    if csrf_token not in tokens:
        tokens.append(csrf_token)
        if len(tokens) > MAX_CSRF_TOKENS:
            tokens = tokens[-MAX_CSRF_TOKENS:]
        session["csrf_tokens"] = tokens
        LOGGER.debug(f"Added CSRF token to session: {csrf_token[:8]}...")

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
            <h1>Welcome to {YorznabClient().ServerNameHtml}</h1>
            {get_started}
            <form id="loginForm" autocomplete="off" method="POST" action="{RouteHandler.AUTH}/login">
                <input type="hidden" name="csrf_token" value="{csrf_token}">
                <input type="text" value="{FASTAPI_USER}" autocomplete="off" name="username" style="display:none">
                <div class="form-group">
                    <div class="password-wrapper">
                        <input type="password" value="{temp_passkey}" autocomplete="off" id="{ID_NAME}" name="passkey" placeholder="{ID_NAME}" required>
                        <button type="button" class="toggle-btn" {"onload" if first_time else ""} id="toggleBtn" aria-label="Toggle password visibility">
                            <span class="eye-icon">👁️</span>
                        </button>
                    </div>
                </div>
                <br>
                {login_button}
            </form>
            {error}
        </div>'''
    
    return Response(
        content=page_template(title="Login", content=content, js="js/auth.js"), 
        status_code=status.HTTP_200_OK, 
        media_type="text/html"
    )


router = APIRouter(prefix=RouteHandler.AUTH, tags=["auth"])

@router.post(f"/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    passkey: str = Form(...),
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token
    
    # Validate CSRF token
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
    
    consume_csrf_token(request, csrf_token_form)
    
    if not KeyStore.is_ready():
        LOGGER.debug(f"Writing keys to file. passkey: {passkey[:3]}...")
        KeyStore.write_keys(passkey)
    
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
    
    LOGGER.debug(f"User authenticated successfully")
    
    try:
        session = request.session
        session["user_id"] = username
        session["is_authenticated"] = True
        session["issued_at"] = int(datetime.now().timestamp())
        if "csrf_tokens" not in session:
            session["csrf_tokens"] = []
    except Exception as e:
        LOGGER.error(f"Failed to set session during login: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "Failed to create session",
                "code": "SESSION_ERROR"
            }
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "success": True,
            "message": "Login successful",
            "redirect": f"{RouteHandler.DASHBOARD}/home"
        }
    )


@router.post(f"/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token
    
    if not consume_csrf_token(request, csrf_token_form):
        LOGGER.warning("Logout CSRF validation failed")
    
    try:
        session = request.session
        session.clear()
        LOGGER.debug("Session cleared during logout")
    except Exception as e:
        LOGGER.error(f"Failed to clear session during logout: {e}")
    
    return RedirectResponse(
        url=f"{RouteHandler.DASHBOARD}/", 
        status_code=status.HTTP_303_SEE_OTHER
    )