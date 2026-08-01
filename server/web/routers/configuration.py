import json
import traceback

from fastapi import APIRouter, Form, HTTPException, Header, Request, Response, requests, status
from fastapi.responses import RedirectResponse
import yaml

# Import modules
from server.entities.YorznabClient import YorznabClient
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.utils.settings import AppSettings, AppSettingsUndefined
from server.web.common import LOGGER, navigation, page_template
from server.web.routers.applications import build_input_template
from server.web.routers.auth import authenticate, consume_csrf_token, logout, update_csrf_headers, validate_csrf, add_csrf_tokens, gen_csrf_token

router = APIRouter(prefix=RouteHandler.DASHBOARD)

@router.get("/configuration", include_in_schema=False)
async def configuration(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)

    config_csrf_tokens = []
    yorznab_csrf_token = gen_csrf_token()
    reset_csrf_token = gen_csrf_token()
    config_csrf_tokens.extend([yorznab_csrf_token, reset_csrf_token])

    input_template = build_input_template(csrf_token=yorznab_csrf_token, client=YorznabClient())

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/configuration')}
            <h1>{YorznabClient().ServerNameHtml} ⚙️ Configuration</h1>

            {input_template}
            <div id="settings" class="text-container" style="display: none;"></div>
            
            <div id="main-menu">
                <div class="text-container">
                    <h2 class="status-container">
                        <span class="status-dot" id="status-dot"></span>
                        Cron Status: <span id="status-label">⏳ Loading...</span>
                    </h2>
                    <div class="info-item">
                        <span class="info-label">
                            <label for="countdown">Job starts in:</label>
                        </span>
                        <span class="info-value countdown-display" id="countdown" data-status="{RouteHandler.STATUS}" title="Job starts in">
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
                    <div class="info-item">
                        <span class="info-label">
                            <label for="server-version">Server version:</label>
                        </span>
                        <span class="info-value" id="server-version" title="Server version"></span>
                    </div>
                    <button class="full-btn action-btn config-btn" type="button" onclick="toggleSettings('template-{YorznabClient().ServerConfigHtml}')">⚙️ Edit Configuration</button>
                </div>
                <br>
                <button id="resetBtn" class="reset-btn" data-reset="{RouteHandler.AUTH}/reset" data-csrf="{reset_csrf_token}" onclick="confirmReset()">
                    🔄 Reset All Keys
                </button>
            </div>
        </div>'''
    
    
    response = Response(content=page_template(title="Credentials", content=content, css=["css/applications.css", "css/configuration.css"], js=["js/credentials.js", "js/cron.js", "js/application.js"]), media_type="text/html")
    add_csrf_tokens(request, config_csrf_tokens)
    return response

# ===== CREDENTIALS ENDPOINT =====

resetRouter = APIRouter(prefix=RouteHandler.AUTH)

@resetRouter.post(f"/reset", tags=["auth"])
async def reset_config(
    request: Request,
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token

    """Reset configuration to default state"""
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Validate CSRF token
    if not validate_csrf(request, csrf_token_form):
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
        LOGGER.error(f"Failed to reset keys: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reset keys")

# ===== SETTINGS ENDPOINT =====

settingsRouter = APIRouter(prefix=RouteHandler.SETTINGS)

@settingsRouter.post(f"/save", tags=["settings"])
async def set_config(
    request: Request,
    config: str,
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token

    """Save configuration"""
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Validate CSRF token
    if not validate_csrf(request, csrf_token_form):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    
    try:
        form_data = await request.form()
        
        # Remove csrf_token if present
        config_data = {k: v for k, v in form_data.items() if k != 'csrf_token'}

        # Check if config is valid
        app_settings = AppSettings(filename=config + '.yaml').exists()
        app_settings.set(config_data)

    except AppSettingsUndefined as e:
        LOGGER.error(f"❌ Configuration file does not exist: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"❌ Configuration file does not exist: {str(e)}")
    except ValueError as e:
        LOGGER.error(f"❌ Failed to parse settings: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to parse settings: {str(e)}")
    except yaml.YAMLError as e:
        LOGGER.error(f"❌ Failed to save invalid content: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to save invalid content: {str(e)}")
    except OSError as e:
        LOGGER.error(f"❌ Failed to save settings: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"❌ Failed to save settings: {str(e)}")
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        LOGGER.error(f"❌ Unknown error occurred while saving settings: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Unknown error occurred while saving settings: {str(e)}")
    
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    consume_csrf_token(request, csrf_token_form)
    # Allow multiple save forms
    return update_csrf_headers(request, response)
