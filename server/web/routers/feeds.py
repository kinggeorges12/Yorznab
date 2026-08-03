import asyncio
import json
import traceback

from fastapi import APIRouter, Form, HTTPException, Header, Request, Response, status
from fastapi.responses import FileResponse, RedirectResponse
import yaml

# Import modules
from server.entities.ArrClient import ArrClient, ArrType
from server.entities.EndpointError import EndpointStatusError
from server.entities.SeerrClient import SeerrClient
from server.entities.YorznabClient import YorznabClient
from server.routers.handler import RouteHandler
from server.utils.feedconfig import FeedConfig, FeedFilter
from server.utils.json_editor import JsonEditor
from server.utils.keystore import KeyStore
from server.web.common import LOGGER, navigation, page_template
from server.web.routers.auth import add_csrf_tokens, authenticate, consume_csrf_token, gen_csrf_token, update_csrf_headers, update_csrf_headers, validate_csrf
from server.web.routers.cache import download_and_cache

dashboard_router = APIRouter(prefix=RouteHandler.DASHBOARD, tags=["web"])

@dashboard_router.get("/feeds", include_in_schema=False)
async def feeds(request: Request):
    if not authenticate(request):
        return RedirectResponse(url=RouteHandler.LOGIN, status_code=status.HTTP_303_SEE_OTHER)

    # Get timestamp for countdown
    ace_css = "cache/css/ace.min.css"
    download_and_cache("https://unpkg.com/ace-css/css/ace.min.css", ace_css)

    # Load each feeds config
    indexer_key = KeyStore.get_key('INDEXER_KEY')
    webhook_key = KeyStore.get_key('WEBHOOK_KEY')
    feed_configs = FeedConfig.feeds()
    feed_csrf_tokens = []
    feed_info = ""
    for feed_config in feed_configs:
        csrf_token = gen_csrf_token()
        feed_csrf_tokens.append(csrf_token)
        feed_info += f'''
            <div class="info-container" id="info-container-{feed_config.feed_name}" data-name="{feed_config.feed_name}">
                <div class="info-item">
                    <span class="info-value edit-feed clickable" name="{feed_config.feed_name}" title="Edit Feed"
                      onclick="showEditor('{feed_config.feed_name}')">✏️
                        <span class="info-label">{feed_config.feed_name}</span>
                    </span>
                    <a title="Movie Search" href="{RouteHandler.INDEXER}/{feed_config.feed_name}?apikey={indexer_key}&t=movie" target="_blank">
                        <span class="info-value">🎬</span>
                    </a>
                    <a title="TV Search" href="{RouteHandler.INDEXER}/{feed_config.feed_name}?apikey={indexer_key}&t=tvsearch" target="_blank">
                        <span class="info-value">📺</span>
                    </a>
                    <span class="clickable" name="{feed_config.feed_name}" title="Publish Feed" data-csrf="{csrf_token}"
                      onclick="publishFeed(event, '{feed_config.feed_name}', '{RouteHandler.PUBLISH}/{feed_config.feed_name}', 'publish-icon-{feed_config.feed_name}')">
                        <span class="info-value" id="publish-icon-{feed_config.feed_name}">🚀</span>
                    </span>
                    <span class="clickable" name="{feed_config.feed_name}" title="Refresh Feed"
                      onclick="refreshFeed(event, '{feed_config.feed_name}', '{RouteHandler.WEBHOOK}?feed={feed_config.feed_name}&apikey={webhook_key}', 'refresh-icon-{feed_config.feed_name}')">
                        <span class="info-value" id="refresh-icon-{feed_config.feed_name}">🔄</span>
                    </span>
                    <span class="clickable" name="{feed_config.feed_name}" title="Delete Feed"
                      onclick="deleteFeed(event, '{feed_config.feed_name}', '{RouteHandler.FEED}/{feed_config.feed_name}', 'info-container-{feed_config.feed_name}', '{csrf_token}')">
                        <span class="info-value" id="delete-icon-{feed_config.feed_name}">🗑️</span>
                    </span>
                </div>
            </div>'''

    editor_csrf_token = gen_csrf_token()
    webhook_csrf_token = gen_csrf_token()
    feed_csrf_tokens.extend([editor_csrf_token, webhook_csrf_token])
    content = f'''
        <div class="app-container">
            {navigation(f'{RouteHandler.DASHBOARD}/feed')}
            <h1>{YorznabClient().ServerNameHtml} 📻 Feeds</h1>
            
            <div id="main-page">
                <div class="text-container">
                    <div class="header-container">
                        <h2>🗃️ Indexers</h2>
                        <a href="https://github.com/kinggeorges12/Yorznab#feeds" title="Help" target="_blank" rel="noopener noreferrer">📖❓</a>
                        <button type="button" class="create-btn" onclick="newYAML('feed-yaml-new'); showEditor();">
                            <span name="new-feed" title="Create New Feed">
                                🆕 Feed
                            </span>
                        </button>
                    </div>
                    {feed_info}
                    <div id="publish-error" class="error-message" style="display: none;"></div>
                </div>
                <button type="submit" action="{RouteHandler.WEBHOOK}/enable" method="post" class="full-btn action-btn feed-btn" data-error="error-webhook" data-csrf="{webhook_csrf_token}" onclick="enableWebhook(this, event)">🪝 Enable Webhook in Jellyseerr</button>
                <p id="error-webhook" class="error-message" style="display: none;">Webhook: Unknown error occurred</p>

            </div>

            <!-- Ace Editor container -->
            <div id="editor-container" style="display: none;" class="yaml-editor-wrapper"
              data-schema="{RouteHandler.FEEDS}/schema"
                data-list="{RouteHandler.FEEDS}/list"
                data-load="{RouteHandler.FEED}"
                data-save="{RouteHandler.FEED}"
                data-csrf="{editor_csrf_token}">
                <textarea id="feed-yaml-new" style="display: none;">{JsonEditor.get_blank()}</textarea>
                <textarea id="feed-yaml-template" style="display: none;">{JsonEditor.get_feed_template()}</textarea>
                <div id="editor-header">
                    <h2>☁️ YAML Editor:
                        <span id="editor-title" contenteditable="true" spellcheck="false" title="Click to edit the feed name">feed</span>
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
    add_csrf_tokens(request, feed_csrf_tokens)
    return response

# ===== WEBHOOK ENDPOINT =====

webhook_router = APIRouter(prefix=RouteHandler.WEBHOOK, tags=["feeds"])

@webhook_router.post("/enable")
async def enable_webhook(
    request: Request,
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
    
    try:

        # Try to save the feed config
        try:
            seerr_config = await SeerrClient().configure_webhook()
            LOGGER.info(f"🪝 Enabled Seerr webhook: {seerr_config}")
        except Exception as e:
            LOGGER.error(f"❌ Error enabling Seerr webhook: {e}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Error enabling Seerr webhook: {str(e)}")
        
        # Create response and consume CSRF token
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        consume_csrf_token(request, csrf_token_form)
        # Allow multiple save forms
        return update_csrf_headers(request, response)
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Unknown error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unknown error: {str(e)}")


# ===== PUBLISH ENDPOINT =====

publishRouter = APIRouter(prefix=RouteHandler.PUBLISH)

@publishRouter.post("/{feed_name:str}", tags=["publish"])
async def set_config(
    request: Request,
    feed_name: str,
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token

    """Publish indexer to Radarr and Sonarr via their API"""
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    # Validate CSRF token
    if not validate_csrf(request, csrf_token_form):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    
    try:
        # Create tasks with names
        tasks = [
            asyncio.create_task(
                ArrClient(ArrType.Radarr).create_torznab_indexer(feed_name=feed_name),
                name='Radarr'
            ),
            asyncio.create_task(
                ArrClient(ArrType.Sonarr).create_torznab_indexer(feed_name=feed_name),
                name='Sonarr'
            ),
        ]    
        # Wait for all
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Gather all exceptions as strings
        error_messages = []
        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                error_messages.append(f"{task.get_name()}: {str(result)}")
                if hasattr(result, 'response_body') and result.response_body:
                    error_messages.append(f"API Response: {result.response_body}")
        # If there were errors, join them into a single string
        if error_messages:
            error_summary = "\n".join(error_messages)
            LOGGER.error(f"❌ Endpoint errors: {error_summary}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"❌ Endpoint returned an error:\n{error_summary}"
            )
    except ValueError as e:
        LOGGER.error(f"❌ Failed to parse feed config: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Failed to parse feed config: {str(e)}")
    except EndpointStatusError as e:
        LOGGER.error(f"❌ Endpoint returned an error: {e}")
        LOGGER.error(f"❌ Response: {e.response_body}")
        raise HTTPException(status_code=e.status_code, detail=f"❌ Endpoint returned an error: {str(e)}")
    except HTTPException as e:
        raise e
    except Exception as e:
        LOGGER.error(traceback.format_exc())
        LOGGER.error(f"❌ Unknown error occurred while publishing feed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"❌ Unknown error occurred while publishing feed: {str(e)}")
    
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    consume_csrf_token(request, csrf_token_form)
    # Allow multiple save forms
    return update_csrf_headers(request, response)


# ===== YAML FILES ENDPOINT =====

feed_router = APIRouter(prefix=RouteHandler.FEED, tags=["feeds"])

@feed_router.get("/{feed_name:str}")
async def load_yaml(request: Request, feed_name: str):
    """
    Load YAML content from a file - returns the raw YAML file
    """
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    
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

@feed_router.post("/{feed_name:str}")
async def save_yaml(
    request: Request,
    feed_name: str,
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
    
    try:
        
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
        consume_csrf_token(request, csrf_token_form)
        # Allow multiple save forms
        return update_csrf_headers(request, response)
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error saving file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save yaml for feed: {feed_name}")


@feed_router.delete("/{feed_name:str}")
async def delete_feed(
    request: Request,
    feed_name: str,
    csrf_token: str = Form(""),
    x_csrf_token: str = Header(None, alias="X-CSRF-Token")
):
    csrf_token_form = x_csrf_token or csrf_token

    """
    Delete a feed by name
    """
    # Authentication - return 401 for APIs
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    
    # Validate CSRF token
    if not validate_csrf(request, csrf_token_form):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
        
    try:
        LOGGER.info(f"🗑️ Deleting feed '{feed_name}': {FeedConfig(feed_name=feed_name)}")
        exists = FeedConfig.delete(feed_name=feed_name)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Feed '{feed_name}' not found"
            )

        # Create response and consume CSRF token
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        consume_csrf_token(request, csrf_token_form)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        LOGGER.error(f"Error deleting feed {feed_name}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete feed: {feed_name}"
        )
    
feeds_router = APIRouter(prefix=RouteHandler.FEEDS, tags=["feeds"])

@feeds_router.get("/schema", include_in_schema=False)
async def load_schema(request: Request):
    """
    Load the JSON schema for the feed configuration editor - returns JSON
    """
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")
    
    # Get blank config schema
    json_editor = JsonEditor(FeedFilter())
    json_schema = json.dumps(json_editor.to_schema())
    return Response(
        content=json_schema,
        media_type="application/json"
    )

@feeds_router.get("/list")
async def list_files(request: Request):
    """
    List available YAML files - returns plain text list
    """
    if not authenticate(request):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed")

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
