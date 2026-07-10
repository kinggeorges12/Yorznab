from fastapi import APIRouter, Response
from fastapi.params import Cookie
from fastapi.responses import RedirectResponse

# Import modules
from server.cron.rssrefresh import CronRunner
from server.routers.handler import RouteHandler
from server.utils.keystore import KeyStore
from server.utils.timezoneaware import TimezoneAware
from server.web.common import TITLE, get_csrf_token, navigation, page_template

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/feeds")
async def feeds(authenticated: str = Cookie(None)):
    if authenticated != "true":
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=303)
    
    token = get_csrf_token()
    
    # Get the current server time
    next_run = CronRunner().next_run
    base_time = TimezoneAware.get_now()
    server_time_str = base_time.strftime('%Y-%m-%d %H:%M:%S')

    # Calculate seconds until next refresh
    seconds_until_next = (next_run - base_time).total_seconds()
    # Ensure we don't show negative time
    if seconds_until_next < 0:
        seconds_until_next = 0

    hours = int(seconds_until_next // 3600)
    minutes = int((seconds_until_next % 3600) // 60)
    seconds = int(seconds_until_next % 60)

    # Format the refresh time
    refresh_time_str = next_run.strftime('%Y-%m-%d %H:%M:%S')

    # Get timestamp for countdown
    target_timestamp = int(next_run.timestamp() * 1000)

    api_key = KeyStore.get_key('API_KEY')
    feed_configs = CronRunner().feed_configs
    feed_info = ""
    for feed_config in feed_configs:
        feed_info += f'''
            <div class="info-item">
                <span class="info-label">{feed_config.config_name}</span>
                <a href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=movie" target="_blank">
                    <span class="info-value" title="Movie Search">🎬</span>
                </a>
                <a href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=tvsearch" target="_blank">
                    <span class="info-value" title="TV Search">📺</span>
                </a>
                <a class="info-linktext" href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=caps" target="_blank">
                    <span class="info-value" title="{feed_config.file}">{feed_config.file}</span>
                </a>
            </div>'''
    
    content = f'''
    <div class="app-container">
        {navigation(f'{RouteHandler.LOGIN}/feed')}
        <h1>{TITLE} 📻 Feeds</h1>
        
        <div class="text-container">
            <h2 class="status-container">
                <span class="status-dot" id="status-dot"></span>
                Cron Status: <span id="status-label">⏳ Loading...</span>
            </h2>
            <div class="info-item">
                <span class="info-label">Refresh starts in:</span>
                <span class="info-value" id="countdown" data-target="{target_timestamp}" title="Refresh starts in">
                    <span class="hours">{hours:02d}</span>
                    <span class="separator">:</span>
                    <span class="minutes">{minutes:02d}</span>
                    <span class="separator">:</span>
                    <span class="seconds">{seconds:02d}</span>
                </span>
            </div>
            <div class="info-item">
                <span class="info-label">Scheduled:</span>
                <span class="info-value" title="Scheduled">{refresh_time_str}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Server time:</span>
                <span class="info-value" title="Server time">{server_time_str}</span>
            </div>
        </div>
        <div class="text-container">
            <h2>API Links</h2>
            {feed_info}
        </div>
    </div>'''
    
    return Response(content=page_template(title="Feeds", content=content, token=token, js="feeds.js"), media_type="text/html")
