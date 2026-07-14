from itertools import accumulate
import random
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.web.common import TITLE, get_csrf_token, navigation, page_template
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/home")
async def home(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    
    token = get_csrf_token()

    # Generate random delays for the ASCII art animation
    random_delays = [round(random.uniform(0.1, 0.3) + round(random.expovariate(8)*2, 1), 1) for _ in range(11)] + [0.1] + [0.1]
    animation_timer = list(reversed(list(accumulate(random_delays))))
    
    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.LOGIN}/home')}
            <h1>{TITLE} 🏠 Home</h1>
            <div class="text-container">
                <h2>Welcome!</h2>
                <br>
                <p>Check out the GitHub repository for updates and information:
                    <a href="https://github.com/kinggeorges12/Yorznab" target="_blank" rel="noopener noreferrer">https://github.com/kinggeorges12/Yorznab</a>
                </p>
                <br><br>
                <p>Stuck? Post an issue:
                    <a href="https://github.com/kinggeorges12/Yorznab/issues" target="_blank" rel="noopener noreferrer">ARRGH HELP ME!</a>
                </p>
            </div>
            <div class="text-container">
                <div id="ascii-container"><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
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
╽ ...a Torznab Indexer that's all YORZ                             <span class="ascii-spacer">            </span>╽</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╿<span class="ascii-spacer">      </span>                                                                  <span class="ascii-spacer">      </span>╿</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╰<span class="ascii-spacer">╼╾╼╾╼╾</span>╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾╼╾<span class="ascii-spacer">╼╾╼╾╼╾</span>╯</pre>
                </div>
            </div>
            <form method="POST" action="{RouteHandler.LOGIN}/logout">
                <button type="submit" class="logout-btn">
                    <span class="btn-icon">➡️</span>
                    <span class="btn-label">Logout</span>
                </button>
            </form>
        </div>'''
    
    return Response(content=page_template(title="Home", content=content, token=token), media_type="text/html")
