from itertools import accumulate
import random
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse

# Import modules
from server.routers.handler import RouteHandler
from server.web.common import TITLE, authenticated, get_csrf_token, navigation, page_template

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/success")
async def login_success(request: Request):
    if not authenticated(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    
    token = get_csrf_token()

    # Generate random delays for the ASCII art animation
    random_delays = [round(random.uniform(0.1, 0.3) + round(random.expovariate(8)*2, 1), 1) for _ in range(11)] + [0.1]
    animation_timer = list(reversed(list(accumulate(random_delays))))
    content = f'''
        <div class="success-container">
            {navigation(f'{RouteHandler.LOGIN}/success')}
            <h1>{TITLE} 🏠 Home</h1>
            <div class="text-container">
                <h2>Welcome! You are logged in.</h2>
                <br>
                <p>Check out the GitHub repository for updates and information:</p>
                <a href="https://github.com/kinggeorges12/Yorznab" target="_blank" rel="noopener noreferrer">https://github.com/kinggeorges12/Yorznab</a>
                <br><br>
                <p>Stuck? Post an issue:</p>
                <a href="https://github.com/kinggeorges12/Yorznab/issues" target="_blank" rel="noopener noreferrer">ARRGH HELP ME!</a>
            </div>
            <div class="text-container">
            <div id="ascii-container"><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╔══════════════════════════════════════════════════════════════════════════════╗</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║                                                                              ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║       ██╗   ██╗ ██████╗ ██████╗ ███████╗███╗   ██╗ █████╗ ██████╗ ██╗        ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║       ╚██╗ ██╔╝██╔═══██╗██╔══██╗╚══███╔╝████╗  ██║██╔══██╗██╔══██╗██║        ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║        ╚████╔╝ ██║   ██║██████╔╝  ███╔╝ ██╔██╗ ██║███████║██████╔╝██║        ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║         ╚██╔╝  ██║   ██║██╔══██╗ ███╔╝  ██║╚██╗██║██╔══██║██╔══██╗╚═╝        ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║          ██║   ╚██████╔╝██║  ██║███████╗██║ ╚████║██║  ██║██████╔╝██╗        ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║          ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═╝  ╚═╝╚═════╝ ╚═╝        ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║══════════════════════════════════════════════════════════════════════════════║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║                                                                              ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
║                                         ...a Torznab Indexer that's all YORZ ║</pre><pre class="ascii-line fade-in" style="animation-delay: {animation_timer.pop()}s">
╚══════════════════════════════════════════════════════════════════════════════╝</pre>

            </div>
        </div>'''
    
    return Response(content=page_template(title="Home", content=content, token=token), media_type="text/html")
