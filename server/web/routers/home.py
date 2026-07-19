from html import escape
from itertools import accumulate
import random
from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.web.common import TITLE, navigation, page_template
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"], include_in_schema=False)

@router.get("/home")
async def home(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)

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
            <h1>{TITLE} 🏠 Home</h1>
            <div class="text-container">
                <h2>Welcome!</h2>
                <br>
                <p>🔍 Check out the GitHub repository for updates and information:
                    <a href="https://github.com/kinggeorges12/Yorznab" target="_blank" rel="noopener noreferrer">
                        <span>https://github.com/kinggeorges12/Yorznab</span>
                    </a>
                </p>
                <br>
                <p>📜 Try out the docs for your Yorznab setup:
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
    
    return Response(content=page_template(title="Home", content=content, css="cache/css/dejavu-sans-mono"), media_type="text/html")
