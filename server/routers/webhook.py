import os

from fastapi import APIRouter, Request, HTTPException, Header, Query, status
from fastapi.responses import JSONResponse
import asyncio

# Import classes
from server.rss.SeerrClient import SeerrClient
from server.utils.settings import AppSettings
from server.rss.ArrClient import ArrClient, ArrType
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.utils.feedconfig import FeedConfig
from server.utils.keystore import KeyStore
import server.rss.builder as rssbuilder

router = APIRouter(prefix=RouteHandler.WEBHOOK, tags=["webhook"])

# Export config vars to globals
SETTINGS = AppSettings(filename='yorznab.yaml')

# Create logger
LOGGER = CustomLogger(name="webhook")

async def run_requests(feed_configs: list[FeedConfig] | None = None, server_type: ArrType | None = None, external_id: str = None) -> int:
    """Run the rssbuilder script to search for torrents and write them to the feed file"""
    global LOGGER, SETTINGS
    try:
        # Build command arguments
        args = ["--log", "--retention", str(SETTINGS.get('cron', 'retention_days'))]
        
        # Add server parameter if specified
        if feed_configs:
            for feed_config in feed_configs:
                args.extend(["--feed", feed_config.feed_name])
        
        # Add server parameter if specified
        if server_type:
            args.extend(["--server", server_type.value])
        
        # Add external ID parameter if specified
        if external_id:
            args.extend(["--external", external_id])

        # Add download parameter from environment variable if set
        download_env = os.environ.get('DOWNLOAD', 'false').lower() not in ['false', 'no']
        if download_env:
            args.extend(["--download"])
        
        # Run the blocking rssbuilder.main() in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, rssbuilder.main, args)
        return result
        
    except Exception as e:
        LOGGER.error(f"Failed to execute requests script: {e}", exc_info=True)
        return 1
    
# Manual run from the web browser
@router.get('')
async def webhook_get(
    feed: str,
    apikey: str = Query(None, description="Webhook key from config file"),
):
    # API key check
    if apikey != KeyStore.get_key("WEBHOOK_KEY"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    
    try:
        feed_config = FeedConfig(feed_name=feed)
        result = await run_requests(feed_configs=[feed_config])
        if result == 0:
            LOGGER.info(f"Successfully processed '{feed_config.feed_name}' feed: {feed_config.file}")
        else:
            raise
    except Exception as e:
        LOGGER.error(f"Error processing '{feed_config.feed_name}' feed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing '{feed_config.feed_name}' feed")
    return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)


# Runs from the Jellyseerr webhook
@router.post('')
async def webhook(request: Request, authorization: str = Header(None)):
    # Check header exists
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    # Expect format: "<API_KEY>"
    elif authorization != KeyStore.get_key("WEBHOOK_KEY"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    # Handle MEDIA_AUTO_APPROVED and MEDIA_APPROVED notifications
    parsed_payload = SeerrClient.parse_payload(payload)

    if parsed_payload.is_valid:

        LOGGER.info(f"Webhook received, processing {parsed_payload.arr_type} requests in background after {SETTINGS.get('cron', 'webhook_wait')} seconds: {payload}")
        
        # Define the background processing function
        async def process_request():
            try:
                # Wait x seconds before processing
                await asyncio.sleep(SETTINGS.get('cron', 'webhook_wait'))
                
                # Call the shared run_requests function
                result = await run_requests(server_type=parsed_payload.arr_type, external_id=parsed_payload.external_param)
                
                if result == 0:
                    LOGGER.info(f"Successfully processed {parsed_payload.arr_type} request for {parsed_payload.external_id} ID: {parsed_payload.external_param}")
                else:
                    LOGGER.error(f"Failed to process {parsed_payload.arr_type} request for {parsed_payload.external_id} ID: {parsed_payload.external_param}")
            except Exception as e:
                LOGGER.error(f"Error processing {parsed_payload.arr_type} request: {str(e)}", exc_info=True)
        
        # Start background task
        asyncio.create_task(process_request())
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_202_ACCEPTED) # 202 Accepted for async processing
        
    elif parsed_payload.is_test:
        LOGGER.info(f"Webhook test received: {payload}")
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)
    else:
        LOGGER.warning(f"Webhook received with no handler: {payload}")
        return JSONResponse(content={"status": "ok"}, status_code=status.HTTP_200_OK)


# Example payloads from Jellyseerr
# {'notification_type': 'TEST_NOTIFICATION', 'event': '', 'subject': 'Test Notification', 'message': 'Check check, 1, 2, 3. Are we coming in clear?', 'image': '', 'media': None, 'request': None, 'issue': None, 'comment': None, 'extra': []}
# Webhook received: {'notification_type': 'MEDIA_AUTO_APPROVED', 'event': 'Series Request Automatically Approved', 'subject': 'A Brand New Show (2025)', 'message': 'Someone requested the first season of a show!', 'image': 'https://image.tmdb.org/image.jpg', 'media': {'media_type': 'tv', 'tmdbId': '223326', 'tvdbId': '466126', 'status': 'PENDING', 'status4k': 'UNKNOWN'}, 'request': {'request_id': '17', 'requestedBy_email': 'jellyseerr_user2', 'requestedBy_username': 'jellyseerr_user2', 'requestedBy_avatar': '/avatarproxy/fcacd22c11aa64e3a2367224bdece3ef?v=1234567890321', 'requestedBy_settings_discordId': '', 'requestedBy_settings_telegramChatId': ''}, 'issue': None, 'comment': None, 'extra': [{'name': 'Requested Seasons', 'value': '1'}]}
# Webhook received: {'notification_type': 'MEDIA_AUTO_APPROVED', 'event': 'Series Request Automatically Approved', 'subject': 'First 2 Seasons of Another Show (2026)', 'message': 'This is the show description.', 'image': 'https://image.tmdb.org/image.jpg', 'media': {'media_type': 'tv', 'tmdbId': '00000', 'tvdbId': '000000', 'status': 'PARTIALLY_AVAILABLE', 'status4k': 'UNKNOWN'}, 'request': {'request_id': '16', 'requestedBy_email': 'jellyseerr_user1', 'requestedBy_username': 'jellyseerr_user1', 'requestedBy_avatar': '/avatarproxy/4548243867c123655494d44fc5d96383?v=1234567890321', 'requestedBy_settings_discordId': '', 'requestedBy_settings_telegramChatId': ''}, 'issue': None, 'comment': None, 'extra': [{'name': 'Requested Seasons', 'value': '1, 2'}]}
# Webhook received: {'notification_type': 'MEDIA_AUTO_APPROVED', 'event': 'Movie Request Automatically Approved', 'subject': 'Another Show Requesting All Seasons (2000)', 'message': 'This show was requested without specifying individual seasons.', 'image': 'https://image.tmdb.org/image.jpg', 'media': {'media_type': 'movie', 'tmdbId': '00000', 'tvdbId': '', 'status': 'PENDING', 'status4k': 'UNKNOWN'}, 'request': {'request_id': '18', 'requestedBy_email': 'jellyseerr_user3', 'requestedBy_username': 'jellyseerr_user3', 'requestedBy_avatar': '/avatarproxy/431d1460d295ecdac033410e7b52b020?v=1234567890321', 'requestedBy_settings_discordId': '', 'requestedBy_settings_telegramChatId': ''}, 'issue': None, 'comment': None, 'extra': []}
