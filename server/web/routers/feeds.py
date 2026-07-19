import json

from fastapi import APIRouter, HTTPException, Header, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
import yaml

# Import modules
from server.routers.handler import RouteHandler
from server.utils.feedconfig import FeedConfig, FeedFilter
from server.utils.json_editor import JsonEditor
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, TITLE, navigation, page_template
from server.web.routers.auth import add_csrf_token, authenticate, consume_csrf_token, gen_csrf_token, validate_csrf
from server.web.routers.cache import download_and_cache

dashboard_router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"])

@dashboard_router.get("/feeds", include_in_schema=False)
async def feeds(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)
    
    csrf_token = gen_csrf_token()

    # Get timestamp for countdown
    ace_css = "cache/css/ace.min.css"
    download_and_cache("https://unpkg.com/ace-css/css/ace.min.css", ace_css)

    # Load each feeds config
    indexer_key = KeyStore.get_key('INDEXER_KEY')
    webhook_key = KeyStore.get_key('WEBHOOK_KEY')
    feed_configs = FeedConfig.feeds()
    feed_info = ""
    for feed_config in feed_configs:
        feed_info += f'''
            <div class="info-container" id="info-container-{feed_config.feed_name}" data-name="{feed_config.feed_name}">
                <div class="info-item">
                    <span class="info-value edit-feed clickable" name="{feed_config.feed_name}" title="Edit Feed"
                      onclick="showEditor('{feed_config.feed_name}')">✏️
                        <span class="info-label">{feed_config.feed_name}</span>
                    </span>
                    <a href="{RouteHandler.INDEXER}/{feed_config.feed_name}?apikey={indexer_key}&t=caps" target="_blank">
                        <span class="info-value" title="Capabilities">ℹ️</span>
                    </a>
                    <a href="{RouteHandler.INDEXER}/{feed_config.feed_name}?apikey={indexer_key}&t=movie" target="_blank">
                        <span class="info-value" title="Movie Search">🎬</span>
                    </a>
                    <a href="{RouteHandler.INDEXER}/{feed_config.feed_name}?apikey={indexer_key}&t=tvsearch" target="_blank">
                        <span class="info-value" title="TV Search">📺</span>
                    </a>
                    <span class="clickable" name="{feed_config.feed_name}" title="Refresh Feed"
                      onclick="refreshFeed(event, '{feed_config.feed_name}', '{RouteHandler.WEBHOOK}?feed={feed_config.feed_name}&apikey={webhook_key}', 'refresh-icon-{feed_config.feed_name}')">
                        <span class="info-value" id="refresh-icon-{feed_config.feed_name}">🔄</span>
                    </span>
                    <span class="clickable" name="{feed_config.feed_name}" title="Delete Feed"
                      onclick="deleteFeed(event, '{feed_config.feed_name}', '{RouteHandler.FEEDS}/{feed_config.feed_name}', 'info-container-{feed_config.feed_name}', '{gen_csrf_token()}')">
                        <span class="info-value" id="delete-icon-{feed_config.feed_name}">🗑️</span>
                    </span>
                </div>
                <div class="info-row">
                    <div class="info-btn")" onclick="copyKey('apiPath-{feed_config.feed_name}')">📋 API Path</div>
                    <div class="key-value" id="apiPath-{feed_config.feed_name}">{f"{RouteHandler.INDEXER}/{feed_config.feed_name}"}</div>
                </div>
            </div>'''

    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/feed')}
            <h1>{TITLE} 📻 Feeds</h1>
            
            <div id="main-page">
                <div class="text-container">
                    <h2 class="status-container">
                        <span class="status-dot" id="status-dot"></span>
                        Cron Status: <span id="status-label">⏳ Loading...</span>
                    </h2>
                    <div class="info-item">
                        <span class="info-label">Refresh starts in:</span>
                        <span class="info-value countdown-display" id="countdown" data-status="{RouteHandler.STATUS}" title="Refresh starts in">
                            <span class="hours"></span>
                            <span class="separator">:</span>
                            <span class="minutes"></span>
                            <span class="separator">:</span>
                            <span class="seconds"></span>
                        </span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Scheduled:</span>
                        <span class="info-value" id="scheduled" title="Scheduled"></span>
                    </div>
                    <div class="info-item">
                        <span class="info-label">Server time:</span>
                        <span class="info-value" id="server-time" title="Server time"></span>
                    </div>
                </div>
                <div class="text-container">
                    <div class="header-container">
                        <h2>🗃️ Indexers</h2>
                        <a href="https://github.com/kinggeorges12/Yorznab#feeds" title="Help" target="_blank" rel="noopener noreferrer">📖❓</a>
                        <button type="button" class="create-btn" onclick="newYAML('feed-yaml-new'); showEditor();">
                            <span class="" name="new_feed" title="Create New Feed">
                                🆕 Feed
                            </span>
                        </button>
                    </div>
                    {feed_info}
                </div>
            </div>

            <!-- Ace Editor container -->
            <div id="editor-container" style="display: none;" class="yaml-editor-wrapper"
              data-schema="{RouteHandler.FEEDS}/schema"
                data-list="{RouteHandler.FEEDS}/list"
                data-load="{RouteHandler.FEEDS}"
                data-save="{RouteHandler.FEEDS}"
                data-csrf="{csrf_token}">
                <textarea id="feed-yaml-new" style="display: none;">{JsonEditor.get_blank()}</textarea>
                <textarea id="feed-yaml-template" style="display: none;">{JsonEditor.get_template()}</textarea>
                <div id="editor-header">
                    <h2>☁️ YAML Editor:
                        <span id="editor-title" contenteditable="true" spellcheck="false" title="Click to edit filename">feed</span>
                        <span id="dirty-indicator">*</span>
                    </h2>
                    <button id="close-editor" class="editor-btn-back" type="button" onclick="hideEditor()">❌ Close</button>
                </div>
                <!-- Toolbar -->
                <div class="yaml-toolbar">
                    <div class="group">
                        <button onclick="newYAML('feed-yaml-new')">➕ New</button>
                        <button onclick="saveYAML()">💾 Save</button>
                        <button onclick="newYAML('feed-yaml-template', 'template')">📝 Template</button>
                        <button onclick="reloadYAML()">💫 Reload</button>
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
                        <button onclick="window.find()">🔍</button>
                        <button onclick="window.replace()">🔃</button>
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
                    <div class="center" style="display: none;">
                        <span id="propertyLegend"></span>
                    </div>
                    <div class="right">
                        <span>Lines: <span class="value" id="totalLines">1</span></span>
                        <span id="currentFileDisplay"></span>
                    </div>
                </div>
                <!-- Toast -->
                <div id="toast" class="yaml-toast"></div>
            </div>
        </div>'''
    
    response = Response(content=page_template(title="Feeds", content=content, css=["css/feeds.css"], js=["js/feeds.js", "js/editor.js", 'cache/ace/ace.js', 'cache/ace/ext-language_tools.js']), media_type="text/html")
    add_csrf_token(request, response, csrf_token)
    return response

router = APIRouter(prefix=RouteHandler.FEEDS, tags=["feeds"])

# ===== YAML FILES ENDPOINT =====

@router.post("/{feed_name:str}")
async def save_yaml(feed_name: str, request: Request,
                    x_csrf_token: str = Header(..., alias="X-CSRF-Token")):
    """
    Save YAML content to a file - returns plain text response
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        # Get CSRF token from header
        csrf_token_header = x_csrf_token
        
        # Validate CSRF token
        if not validate_csrf(request, csrf_token_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
        
        # Save yaml
        body_content = await request.body()

        # Try to save the feed config
        try:
            feed_config = FeedConfig.save(feed_name=feed_name, yaml_data=body_content.decode('utf-8'))
            LOGGER.info(f"💾 Saved feed '{feed_name}': {feed_config}")
        except yaml.YAMLError as e:
            LOGGER.error(f"❌ Invalid YAML content: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to save invalid YAML content: {str(e)}")
        except OSError as e:
            LOGGER.error(f"❌ Cannot save feed config: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"❌ Failed to save feed config: {str(e)}")
        except Exception as e:
            LOGGER.error(f"❌ Cannot parse feed config: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to parse feed config: {str(e)}")
        
        # Create response and consume CSRF token
        response = Response(
            content=json.dumps({"message": f"✅ Feed saved successfully: {feed_name}"}),
            status_code=status.HTTP_200_OK,
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
        LOGGER.error(f"Error saving file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save yaml for feed: {feed_name}")


@router.delete("/{feed_name:str}")
async def delete_feed(feed_name: str, request: Request,
                      x_csrf_token: str = Header(..., alias="X-CSRF-Token")):
    """
    Delete a feed by name
    """
    # Authentication - return 401 for APIs
    if not authenticate(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Get CSRF token from header
        csrf_token_header = x_csrf_token
        
        # Validate CSRF token
        if not validate_csrf(request, csrf_token_header):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
        
        LOGGER.info(f"🗑️ Deleting feed '{feed_name}': {FeedConfig(feed_name=feed_name)}")
        exists = FeedConfig.delete(feed_name=feed_name)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed '{feed_name}' not found"
            )

        # Create response and consume CSRF token
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        consume_csrf_token(request, response, csrf_token_header)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error deleting feed {feed_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete feed: {feed_name}"
        )
    
@router.get("/schema", include_in_schema=False)
async def load_schema(request: Request):
    """
    Load the JSON schema for the feed configuration editor - returns JSON
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)
    # Get blank config schema
    json_editor = JsonEditor(FeedFilter())
    json_schema = json.dumps(json_editor.to_schema())
    return Response(
        content=json_schema,
        media_type="application/json"
    )

@router.get("/{feed_name:str}")
async def load_yaml(request: Request, feed_name: str):
    """
    Load YAML content from a file - returns the raw YAML file
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)
    
    try:
        feed_config = FeedConfig(feed_name)
        
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

@router.get("/list")
async def list_files(request: Request):
    """
    List available YAML files - returns plain text list
    """
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.DASHBOARD, status_code=status.HTTP_303_SEE_OTHER)

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
