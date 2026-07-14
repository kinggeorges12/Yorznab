from dataclasses import asdict
import json
from xml.etree.ElementTree import indent

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import RedirectResponse

# Import modules
from server.cron.rssrefresh import CronRunner
from server.routers.handler import RouteHandler
from server.utils.feedconfig import FeedConfig
from server.utils.keystore import KeyStore
from server.utils.timezoneaware import TimezoneAware
from server.web.common import TITLE, download_and_cache, get_csrf_token, navigation, page_template
from server.web.guifier import Guifier
from server.web.routers.auth import authenticate

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/feeds")
async def feeds(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    
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

    guifier = download_and_cache("https://cdn.jsdelivr.net/npm/guifier/dist/Guifier.js", "cache/Guifier.js")
    json_editor = download_and_cache("https://cdn.jsdelivr.net/npm/@json-editor/json-editor@latest/dist/jsoneditor.js", "cache/JsonEditor.js")

    api_key = KeyStore.get_key('API_KEY')
    feed_template = FeedConfig('feed.yaml.sample')
    feed_configs = CronRunner().feed_configs
    feed_info = ""
    for feed_config in feed_configs:
        feed_info += f'''
            <div class="info-item">
                <button type="button" class="feed-button" name="{feed_config.config_name}">✏️{feed_config.config_name}</button>
                <a href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=movie" target="_blank">
                    <span class="info-value" title="Movie Search">🎬</span>
                </a>
                <a href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=tvsearch" target="_blank">
                    <span class="info-value" title="TV Search">📺</span>
                </a>
                <textarea name="{feed_config.config_name}" class="guifier" style="ddisplay: none;">{Guifier(feed_config.config)}</textarea>
            </div>'''
                # <span class="info-label">{feed_config.config_name}</span>
                # <a class="info-linktext" href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=caps" target="_blank">
                #     <span class="info-value" title="{feed_config.file}">{feed_config.file}</span>
                # </a>
    
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
                    <span class="info-value" id="countdown" data-status="{RouteHandler.STATUS}" data-target="{target_timestamp}" title="Refresh starts in">
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
            <textarea name="guifier-output" style="width: 100%; height: 200px;"></textarea>
            <button type="button" id="new-feed-button" onclick="showYaml('feed.yaml.sample')">➕ New</button>
            <button type="button" id="template-feed-button" onclick="showYaml('feed.yaml.sample')">📝 Template</button>
            <button type="button" id="save-feed-button" onclick="saveYaml()">💾 Save</button>
            <textarea name="{feed_template.config_name}" class="guifier" style="width: 100%; height: 200px; ddisplay: none;">{Guifier(feed_template.config)}</textarea>
            <div id="guifier"></div>
        </div>'''
    
    return Response(content=page_template(title="Feeds", content=content, token=token, module={guifier: 'Guifier'}, js="js/feeds.js"), media_type="text/html")
