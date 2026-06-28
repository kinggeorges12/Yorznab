import os
from fastapi import APIRouter, Request, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from server.routers.handler import RouteHandler
from utils.settings import AppSettings
from utils.keystore import KeyStore
import rss.builder
import asyncio

# Load libraries
from server.rss.ArrClient import ArrClient, ArrType

router = APIRouter()

# Export config vars to globals
SETTINGS = AppSettings(filename='yorznab.yaml')

async def run_requests(server_type: ArrType | None = None, external_id: str = None) -> int:
    """Run the rssbuilder script to search for torrents and write them to the feed file"""
    try:
        # Build command arguments
        args = ["--log", "--publish", SETTINGS.get('feed', 'file'), "--retention", str(SETTINGS.get('rss', 'retention_days'))]
        
        # Add server parameter if specified
        if server_type:
            args.extend(["--server", server_type.value])
        
        # Add external ID parameter if specified
        if external_id:
            args.extend(["--external", external_id])
        
        # Run the blocking rssbuilder.main() in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, rss.builder.main, args)
        return result
        
    except Exception as e:
        print(f"Failed to execute requests script: {e}", exc_info=True)
        return 1

# Manual run from the web browser
@router.get(RouteHandler.WEBHOOK)
async def webhook_get(
    server: str = Query(None, description="Server name to process (Radarr or Sonarr)"),
    id: str = Query(None, description="External ID for the wanted video (TMDB/TVDB ID)")
):
    """Run the requests.py script to search for torrents and write them to the feed file"""
    result = await run_requests(server_type=ArrType(server), external_id=id)
    
    if result == 0:
        message = "Requests script executed successfully"
        if server:
            message += f" for {server}"
        if id is not None:
            message += f" with external ID {id}"
        
        return JSONResponse(
            content={
                "status": "success", 
                "message": message
            }, 
            status_code=200
        )
    else:
        return JSONResponse(
            content={
                "status": "error", 
                "message": "Requests script failed",
                "exit_code": result
            }, 
            status_code=500
        )

# Runs from the Jellyseerr webhook
@router.post(RouteHandler.WEBHOOK)
async def webhook(request: Request, authorization: str = Header(None)):
    # Check header exists
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    # Expect format: "<API_KEY>"
    elif authorization != KeyStore.get_key("WEBHOOK_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Handle MEDIA_AUTO_APPROVED and MEDIA_APPROVED notifications
    if payload.get("notification_type") in ["MEDIA_AUTO_APPROVED", "MEDIA_APPROVED"] and payload.get("media"):
        media = payload["media"]
        media_type = media.get("media_type")
        
        # Initialize ArrClient based on Jellyseerr media type
        arr = ArrClient.init_jellyseerr(media_type)
        
        # Set initial to the database ID, then process seasons for TV
        external_id = arr.ExternalId
        if(arr.ServerType == ArrType.Sonarr):
            # Get requested seasons from extra data
            requested_seasons = []
            for extra_item in payload.get("extra", []):
                if extra_item.get("name") == "Requested Seasons":
                    requested_seasons += extra_item.get("value")
            # Build external parameter with tvdbId and season
            if requested_seasons:
                external_id = f"{arr.ExternalId}:{','.join(str(s) for s in requested_seasons)}"

        print(f"Webhook received, processing {arr.TypeName} requests in background after {SETTINGS.get('rss', 'webhook_wait')} seconds: {payload}")
        
        # Define the background processing function
        async def process_request():
            try:
                # Wait x seconds before processing
                await asyncio.sleep(SETTINGS.get('rss', 'webhook_wait'))
                
                # Call the shared run_requests function
                result = await run_requests(server_type=arr.ServerType, external_id=external_id)
                
                if result == 0:
                    print(f"Successfully processed {arr.ServerName} request for {arr.ExternalDb} ID: {external_id}")
                else:
                    print(f"Failed to process {arr.ServerName} request for {arr.ExternalDb} ID: {external_id}")
            except Exception as e:
                print(f"Error processing {arr.ServerName} request: {str(e)}")
        
        # Start background task
        asyncio.create_task(process_request())
        return JSONResponse(content={"status": "ok"}, status_code=202) # 202 Accepted for async processing
        
    else:
        print(f"Webhook received with no handler: {payload}")
        return JSONResponse(content={"status": "ok"}, status_code=200)


# Example payloads from Jellyseerr
# {'notification_type': 'TEST_NOTIFICATION', 'event': '', 'subject': 'Test Notification', 'message': 'Check check, 1, 2, 3. Are we coming in clear?', 'image': '', 'media': None, 'request': None, 'issue': None, 'comment': None, 'extra': []}
# Webhook received: {'notification_type': 'MEDIA_AUTO_APPROVED', 'event': 'Series Request Automatically Approved', 'subject': 'A Brand New Show (2025)', 'message': 'Someone requested the first season of a show!', 'image': 'https://image.tmdb.org/image.jpg', 'media': {'media_type': 'tv', 'tmdbId': '223326', 'tvdbId': '466126', 'status': 'PENDING', 'status4k': 'UNKNOWN'}, 'request': {'request_id': '17', 'requestedBy_email': 'jellyseerr_user2', 'requestedBy_username': 'jellyseerr_user2', 'requestedBy_avatar': '/avatarproxy/fcacd22c11aa64e3a2367224bdece3ef?v=1234567890321', 'requestedBy_settings_discordId': '', 'requestedBy_settings_telegramChatId': ''}, 'issue': None, 'comment': None, 'extra': [{'name': 'Requested Seasons', 'value': '1'}]}
# Webhook received: {'notification_type': 'MEDIA_AUTO_APPROVED', 'event': 'Series Request Automatically Approved', 'subject': 'Season 2 of Another Show (2026)', 'message': 'This is the show description.', 'image': 'https://image.tmdb.org/image.jpg', 'media': {'media_type': 'tv', 'tmdbId': '00000', 'tvdbId': '000000', 'status': 'PARTIALLY_AVAILABLE', 'status4k': 'UNKNOWN'}, 'request': {'request_id': '16', 'requestedBy_email': 'jellyseerr_user1', 'requestedBy_username': 'jellyseerr_user1', 'requestedBy_avatar': '/avatarproxy/4548243867c123655494d44fc5d96383?v=1234567890321', 'requestedBy_settings_discordId': '', 'requestedBy_settings_telegramChatId': ''}, 'issue': None, 'comment': None, 'extra': [{'name': 'Requested Seasons', 'value': '2'}]}
# Webhook received: {'notification_type': 'MEDIA_AUTO_APPROVED', 'event': 'Movie Request Automatically Approved', 'subject': 'Another Show Requesting All Seasons (2000)', 'message': 'This show was requested without specifying individual seasons.', 'image': 'https://image.tmdb.org/image.jpg', 'media': {'media_type': 'movie', 'tmdbId': '00000', 'tvdbId': '', 'status': 'PENDING', 'status4k': 'UNKNOWN'}, 'request': {'request_id': '18', 'requestedBy_email': 'jellyseerr_user3', 'requestedBy_username': 'jellyseerr_user3', 'requestedBy_avatar': '/avatarproxy/431d1460d295ecdac033410e7b52b020?v=1234567890321', 'requestedBy_settings_discordId': '', 'requestedBy_settings_telegramChatId': ''}, 'issue': None, 'comment': None, 'extra': []}
