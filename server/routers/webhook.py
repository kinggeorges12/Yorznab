from fastapi import APIRouter, Request, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from utils.settings import load_settings
import rss.builder
import threading
import asyncio

router = APIRouter()

# Define defaults
DEFAULTS = {
    "WEBHOOK_KEY": "",
    "WEBHOOK_ENDPOINT": "/webhook",
    "WEBHOOK_WAIT": 30,
    "FEED_FILE": "/app/data/torrents.json",
    "RSS_RETENTION_DAYS": 365,
}
# Export config vars to globals
globals().update(load_settings(DEFAULTS, ["WEBHOOK_KEY"]))

async def run_requests(type_name: str = None, external_id: str = None) -> int:
    """Run the rssbuilder script to search for torrents and write them to the feed file"""
    try:
        # Build command arguments
        args = ["--log", "--publish", globals().get('FEED_FILE'), "--retention", str(globals().get('RSS_RETENTION_DAYS'))]
        
        # Add type parameter if specified
        if type_name and type_name in ['Movies', 'TV']:
            args.extend(["--name", type_name])
        
        # Add external ID parameter if specified
        if external_id:
            args.extend(["--external", external_id])
        
        # Run the blocking rssbuilder.main() in a thread pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, rss.builder.main, args)
        return result
        
    except Exception as e:
        print(f"Failed to execute requests script: {str(e)}")
        return 1

@router.get("/webhook")
async def webhook_get(
    type: str = Query(None, description="Type of content to search for: 'Movies' or 'TV'"),
    id: str = Query(None, description="External ID for the wanted video (TMDB/TVDB ID)")
):
    """Run the requests.py script to search for torrents and write them to the feed file"""
    result = await run_requests(type_name=type, external_id=id)
    
    if result == 0:
        message = "Requests script executed successfully"
        if type:
            message += f" for {type}"
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

@router.post("/webhook")
async def webhook(request: Request, authorization: str = Header(None)):
    # Check header exists
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    # Expect format: "<API_KEY>"
    elif authorization != WEBHOOK_KEY:  # pyright: ignore[reportUndefinedVariable]
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
        
        if media_type == "movie":
            type_name = "Movies"
            db_type = "TMBD"
            external_id = media.get("tmdbId")
        elif media_type == "tv":
            type_name = "TV"
            db_type = "TVDB"
            tvdb_id = media.get("tvdbId")
            # Get requested seasons from extra data
            requested_seasons = []
            for extra_item in payload.get("extra", []):
                if extra_item.get("name") == "Requested Seasons":
                    requested_seasons += extra_item.get("value")

            # Build external parameter with tvdbId and season
            if requested_seasons:
                external_id = f"{tvdb_id}:{','.join(str(s) for s in requested_seasons)}"
            else:
                external_id = tvdb_id

        print(f"Webhook received, processing {type_name} requests in background after {globals().get('WEBHOOK_WAIT')} seconds: {payload}")
        
        # Define the background processing function
        async def process_request():
            try:
                # Wait x seconds before processing
                await asyncio.sleep(globals().get('WEBHOOK_WAIT', 30))
                
                # Call the shared run_requests function
                result = await run_requests(type_name=type_name, external_id=external_id)
                
                if result == 0:
                    print(f"Successfully processed {type_name} request for {db_type} ID: {external_id}")
                else:
                    print(f"Failed to process {type_name} request for {db_type} ID: {external_id}")
            except Exception as e:
                print(f"Error processing {type_name} request: {str(e)}")
        
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
