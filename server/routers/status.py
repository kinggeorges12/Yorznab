from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

# Import local modules
from server.cron.rssrefresh import CronRunner
from server.routers.handler import RouteHandler

router = APIRouter()

# Docker status check
@router.get(RouteHandler.STATUS)
async def cron_status():
    cron_status = CronRunner.status()
    match cron_status:
        case "Initializing":
            return JSONResponse(content={"status": "healthy", "active": True, "label": "⏳ Initializing"}, status_code=status.HTTP_200_OK)
        case "Started":
            return JSONResponse(content={"status": "healthy", "active": True, "label": "🚀 Started"}, status_code=status.HTTP_200_OK)
        case "Running":
            return JSONResponse(content={"status": "healthy", "active": True, "label": "🤖 Running"}, status_code=status.HTTP_200_OK)
        case "Sleeping":
            return JSONResponse(content={"status": "healthy", "active": False, "label": "💤 Sleeping"}, status_code=status.HTTP_200_OK)
        case "Failed":
            return JSONResponse(content={"status": "unhealthy", "active": None, "label": "🔥 Failure"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JSONResponse(content={"status": "unhealthy", "active": None, "label": "❓ Unknown"}, status_code=status.HTTP_200_OK)
