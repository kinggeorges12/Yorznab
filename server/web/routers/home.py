from html import escape
from itertools import accumulate
import random
from fastapi import APIRouter, HTTPException, Header, Request, Response, status
from fastapi.responses import RedirectResponse
import yaml

# Import modules
from server.entities.Yorznab import YorznabConfig
from server.routers.handler import RouteHandler
from server.utils.settings import AppSettings
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
            <h1>{YorznabConfig().ServerName} 🏠 Home</h1>
            <div class="text-container">
                <h2>Welcome to
                    <div id="YorznabEditContainer" class="home-renamer" data-save="{RouteHandler.SETTINGS}/rename/" data-csrf="{csrf_token}">
                        <span id="YorznabTitle">{YorznabConfig().ServerName}</span>
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
async def rename_yorznab(request: Request, yorznab_name: str,
                    x_csrf_token: str = Header(..., alias="X-CSRF-Token")):
    """
    Save YAML content to a file - returns plain text response
    """
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    
    try:
        # Get CSRF token from header
        csrf_token_header = x_csrf_token
        
        # Validate CSRF token
        if not validate_csrf(request, csrf_token_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")

        # Try to save the yorznab config
        try:
            if not yorznab_name or not yorznab_name.strip():
                raise ValueError("Feed name cannot be blank")
            SETTINGS = AppSettings(filename='yorznab.yaml')
            SETTINGS.set(f"feed: title", yorznab_name)
        except yaml.YAMLError as e:
            LOGGER.error(f"❌ Invalid YAML content: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to save invalid YAML content: {str(e)}")
        except OSError as e:
            LOGGER.error(f"❌ Cannot save yorznab config: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"❌ Failed to save yorznab config: {str(e)}")
        except Exception as e:
            LOGGER.error(f"❌ Cannot parse yorznab config: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to parse yorznab config: {str(e)}")
        
        # Create response and consume CSRF token
        response = Response(
            status_code=status.HTTP_204_NO_CONTENT,
            media_type="application/json"
        )
        consume_csrf_token(request, response, csrf_token_header)
        # Allow multiple save forms
        csrf_token = gen_csrf_token()
        add_csrf_token(request, response, csrf_token)
        response.headers["X-CSRF-Token"] = csrf_token
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Unknown error occurred while renaming yorznab: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to rename yorznab: {yorznab_name}")

