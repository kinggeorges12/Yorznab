from dataclasses import asdict
import json

from fastapi import APIRouter, Body, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
import yaml

# Import modules
from server.cron.rssrefresh import CronRunner
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.utils.feedconfig import FeedConfig, FeedFilter
from server.utils.json_editor import JSONEditor
from server.utils.keystore import KeyStore
from server.utils.timezoneaware import TimezoneAware
from server.web.common import TITLE, get_csrf_token, navigation, page_template
from server.web.routers.auth import authenticate
from server.web.routers.cache import download_and_cache

LOGGER = CustomLogger(name="feeds")

router = APIRouter(prefix=RouteHandler.LOGIN, tags=["web"])

@router.get("/feeds")
async def feeds(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    
    token = get_csrf_token()
    
    # Get the current server time
    next_run = CronRunner().next_run
    base_time = TimezoneAware.now()
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
    ace_css = "cache/css/ace.min.css"
    download_and_cache("https://unpkg.com/ace-css/css/ace.min.css", ace_css)

    # Load each feeds config
    api_key = KeyStore.get_key('API_KEY')
    feed_configs = CronRunner().feed_configs
    feed_info = ""
    for feed_config in feed_configs:
        feed_info += f'''
            <div class="info-item">
                <button type="button" class="feed-button" name="{feed_config.feed_name}" onclick="loadFeed(this.name)">✏️{feed_config.feed_name}</button>
                <a href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=movie" target="_blank">
                    <span class="info-value" title="Movie Search">🎬</span>
                </a>
                <a href="{RouteHandler.API}/{feed_config.file}?apikey={api_key}&t=tvsearch" target="_blank">
                    <span class="info-value" title="TV Search">📺</span>
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

            <!-- Ace Editor container -->
            <div id="editor-container" class="yaml-editor-wrapper" data-schema="{RouteHandler.LOGIN}/feeds/schema" data-list="{RouteHandler.LOGIN}/feeds/list" data-load="{RouteHandler.LOGIN}/feeds/load" data-save="{RouteHandler.LOGIN}/feeds/save">
                <!-- Toolbar -->
                <div class="yaml-toolbar">
                    <div class="group">
                        <button onclick="newYAML()">➕ New</button>
                        <button onclick="saveYAML()">💾 Save</button>
                        <button onclick="loadYAML()">📝 Template</button>
                        <label for="fileSelector">📂 File:</label>
                        <select id="fileSelector" onchange="selectFile()">
                            <!-- Populated from list endpoint -->
                        </select>
                    </div>
                    <div class="group">
                        <label for="fontSize">Size:</label>
                        <input type="number" id="fontSize" value="13" min="8" max="30" 
                            onchange="changeFontSize(this.value)">
                        <button onclick="undo()">↩</button>
                        <button onclick="redo()">↪</button>
                        <button onclick="editor.execCommand('find')">🔍</button>
                        <button onclick="editor.execCommand('replace')">🔃</button>
                        <button onclick="showSuggestions()">💡 Suggest</button>
                        <button onclick="toggleWrap()" id="wrapBtn">🔠 Wrap</button>
                    </div>
                </div>
                
                <!-- Editor -->
                <div class="yaml-editor-area">
                    <div id="editor"></div>
                </div>
                
                <!-- Status Bar -->
                <div class="yaml-statusbar">
                    <div class="left">
                        <span>Ln: <span class="value" id="cursorLine">1</span></span>
                        <span>Col: <span class="value" id="cursorCol">1</span></span>
                        <span>Sel: <span class="value" id="selectedChars">0</span></span>
                    </div>
                    <div class="center">
                        <span id="propertyLegend"></span>
                    </div>
                    <div class="right">
                        <span>Lines: <span class="value" id="totalLines">1</span></span>
                        <span id="currentFileDisplay"></span>
                    </div>
                </div>
            </div>

            <!-- Toast -->
            <div id="toast" class="yaml-toast"></div>
        </div>'''
    
    return Response(content=page_template(title="Feeds", content=content, token=token, css=["css/feeds.css"], js=["js/feeds.js", "js/editor.js", 'cache/ace/ace.js', 'cache/ace/ext-language_tools.js']), media_type="text/html")


# ===== YAML FILES ENDPOINT =====

@router.post("/feeds/save/{feedname:str}")
async def save_yaml(feedname: str, request: Request):
    """
    Save YAML content to a file - returns plain text response
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    try:
        # Save yaml
        body_content = await request.body()

        # Try to load the feed config
        feed_config = FeedConfig(feedname)
        try:
            yaml_content = yaml.safe_load(body_content)  # Validate YAML
            feed_config.load(yaml_content)  # Load into config object
        except yaml.YAMLError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid YAML content: {str(e)}")
        feed_config.save(body_content.decode('utf-8'))
        
        # Return success message
        return Response(
            content=json.dumps({"message": f"✅ Feed saved successfully: {feedname}"}),
            status_code=status.HTTP_200_OK,
            media_type="application/json"
        )
        
    except Exception as e:
        LOGGER.error(f"Error saving file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save yaml for feed: {feedname}")

@router.get("/feeds/schema")
async def load_schema(request: Request):
    """
    Load the JSON schema for the feed configuration editor - returns JSON
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    # Get blank config schema
    json_editor = JSONEditor(FeedFilter())
    json_schema = json.dumps(json_editor.to_schema())
    return Response(
        content=json_schema,
        media_type="application/json"
    )

@router.get("/feeds/load/{feedname:str}")
async def load_yaml(request: Request, feedname: str):
    """
    Load YAML content from a file - returns the raw YAML file
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        feed_config = FeedConfig(feedname)
        
        if not feed_config.config_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        
        # Return the raw YAML file as plain text
        return FileResponse(
            path=feed_config.config_path,
            filename=feed_config.feed_filename,
            media_type="text/yaml"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error loading file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error loading file: {str(e)}")

@router.get("/feeds/list")
async def list_files(request: Request):
    """
    List available YAML files - returns plain text list
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)

    try:
        file_list = [feed.feed_name for feed in FeedConfig.feeds()]
        
        return Response(
            content=json.dumps(file_list) if file_list else "No YAML files found",
            status_code=status.HTTP_200_OK,
            media_type="application/json"
        )
        
    except Exception as e:
        LOGGER.error(f"Error listing files: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error listing files: {str(e)}")
