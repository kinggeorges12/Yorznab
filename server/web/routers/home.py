from html import escape
from itertools import accumulate
import random
import traceback
from fastapi import APIRouter, Form, HTTPException, Header, Request, Response, status
from fastapi.responses import RedirectResponse
import yaml

# Import modules
from server.entities.YorznabClient import YorznabClient
from server.routers.handler import RouteHandler
from server.utils.settings import AppSettings, AppSettingsUndefined
from server.web.common import LOGGER, navigation, page_template
from server.web.routers.auth import add_csrf_token, authenticate, consume_csrf_token, gen_csrf_token, validate_csrf

router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"], include_in_schema=False)

@router.get("/home")
async def home(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)

    csrf_token = gen_csrf_token()

    # Generate random delays for the ASCII art animation
    random_delays = [round(random.uniform(0.1, 0.3) + round(random.expovariate(8)*2, 1), 1) for _ in range(11)] + [0.1] + [0.1]
    animation_timer = list(reversed(list(accumulate(random_delays))))

    home_content = f'''<pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╭<span class="ascii-spacer">╼╾╼╾╼╾</span>╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾<span class="ascii-spacer">╼╾╼╾╼╾</span>╮</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╽<span class="ascii-spacer">      </span>                                                                  <span class="ascii-spacer">      </span>╽</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╿<span class="ascii-spacer">      </span> ██╮   ██╮ ██████╮ ██████╮ ███████╮███╮   ██╮ █████╮ ██████╮ ██╮  <span class="ascii-spacer">      </span>╿</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╽<span class="ascii-spacer">      </span> ╰██╮ ██╭╯██╭╼╾╼██╮██╭╼╾██╮╰╼╾███╭╯████╮  ██╽██╭╼╾██╮██╭╼╾██╮██╽  <span class="ascii-spacer">      </span>╽</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╿<span class="ascii-spacer">      </span>  ╰████╭╯ ██╽   ██╽██████╭╯  ███╭╯ ██╭██╮ ██╿███████╿██████╭╯██╿  <span class="ascii-spacer">      </span>╿</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╽<span class="ascii-spacer">      </span>   ╰██╭╯  ██╿   ██╿██╭╼╾██╮ ███╭╯  ██╽╰██╮██╽██╭╼╾██╽██╭╼╾██╮╰╼╯  <span class="ascii-spacer">      </span>╽</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╿<span class="ascii-spacer">      </span>    ██╿   ╰██████╭╯██╿  ██╿███████╮██╿ ╰████╿██╿  ██╿██████╭╯██╮  <span class="ascii-spacer">      </span>╿</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╽<span class="ascii-spacer">      </span>    ╰╼╯    ╰╼╾╼╾╼╯ ╰╼╯  ╰╼╯╰╼╾╼╾╼╾╯╰╼╯  ╰╼╾╼╯╰╼╯  ╰╼╯╰╼╾╼╾╼╯ ╰╼╯  <span class="ascii-spacer">      </span>╽</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╟<span class="ascii-spacer">╼╾╼╾╼╾</span>╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾<span class="ascii-spacer">╼╾╼╾╼╾</span>╢</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╿<span class="ascii-spacer">      </span>                                                                  <span class="ascii-spacer">      </span>╿</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╽<span class="ascii-spacer">      </span> ...a Torznab Indexer that's all YORZ                             <span class="ascii-spacer">      </span>╽</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╿<span class="ascii-spacer">      </span>                                                                  <span class="ascii-spacer">      </span>╿</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╰<span class="ascii-spacer">╼╾╼╾╼╾</span>╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾<span class="ascii-spacer">╼╾╼╾╼╾</span>╯</pre>
'''
    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/home')}
            <h1>{YorznabClient().ServerNameHtml} 🏠 Home</h1>
            <div class="text-container">
                <h2>Welcome to
                    <div id="YorznabEditContainer" class="home-renamer" data-save="{RouteHandler.SETTINGS}/rename/" data-csrf="{csrf_token}">
                        <span id="YorznabTitle">{YorznabClient().ServerNameHtml}</span>
                        <input id="YorznabInput" type="text" placeholder="Yorznab" />
                        <button class="edit-btn">✏️</button>
                    </div>
                </h2>
                <br>
                <p>🔍 Check out the GitHub repository for updates and information:
                    <a href="https://github.com/kinggeorges12/Yorznab" target="_blank" rel="noopener noreferrer">
                        <span>https://github.com/kinggeorges12/Yorznab</span>
                    </a>
                </p>
                <br>
                <p>📜 Try out the API docs for your setup:
                    <a href="/docs" target="_blank" rel="noopener noreferrer">
                        <span>{request.base_url}docs</span>
                    </a>
                </p>
                <br>
                <p>💬 Stuck? Post an issue:
                    <a href="https://github.com/kinggeorges12/Yorznab/issues" target="_blank" rel="noopener noreferrer">
                        <span>ARRGH HELP ME!</span>
                    </a>
                </p>
            </div>
            <div class="text-container">
                <div id="ascii-container">
                {home_content}
                </div>
            </div>
            <form method="POST" action="{RouteHandler.AUTH}/logout">
                <button type="submit" class="logout-btn">
                    <span class="btn-icon">➡️</span>
                    <span class="btn-label">Logout</span>
                </button>
            </form>
        </div>'''
    
    response = Response(content=page_template(title="Home", content=content, css=["cache/css/dejavu-sans-mono", "css/home.css"], js="js/home.js"), media_type="text/html")
    add_csrf_token(request, response, csrf_token)
    return response

settings_router = APIRouter(prefix=RouteHandler.SETTINGS, tags=["settings"])

@settings_router.post("/rename/{yorznab_name:str}")
async def rename_yorznab(
    request: Request,
    yorznab_name: str,
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token

    """
    Save YAML content to a file - returns plain text response
    """
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    
    # Validate CSRF token
    if not validate_csrf(request, csrf_token_form):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

    # Try to save the yorznab config
    try:
        if not yorznab_name or not yorznab_name.strip():
            raise ValueError("Instance name cannot be blank")
        config_data = {"ServerName": yorznab_name}
        app_settings = AppSettings(filename='Instance.yaml').exists()
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
   
    # Create response and consume CSRF token
    response = Response(
        status_code=status.HTTP_204_NO_CONTENT,
        media_type="application/json"
    )
    consume_csrf_token(request, response, csrf_token_form)
    # Allow multiple save forms
    csrf_token = gen_csrf_token()
    add_csrf_token(request, response, csrf_token)
    response.headers["X-CSRF-Token"] = csrf_token
    return response
