from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

# Import local modules
from server.cron.rssrefresh import CronRunner
from server.routers.handler import RouteHandler
from server.utils.timeformatter import TimezoneAware, IsoTimeFormatter

router = APIRouter()

# Docker status check
@router.get(RouteHandler.STATUS)
async def cron_status():
    cron_status = CronRunner.status()
    cron_next = TimezoneAware.isoformat(CronRunner.next_run())
    server_time = TimezoneAware.isoformat()
    match cron_status:
        case "Initializing":
            return JSONResponse(content={"status": "healthy", "active": True, "label": "⏳ Initializing", "time": server_time, "next": cron_next}, status_code=status.HTTP_200_OK)
        case "Started":
            return JSONResponse(content={"status": "healthy", "active": True, "label": "🚀 Started", "time": server_time, "next": cron_next}, status_code=status.HTTP_200_OK)
        case "Running":
            return JSONResponse(content={"status": "healthy", "active": True, "label": "🤖 Running", "time": server_time, "next": cron_next}, status_code=status.HTTP_200_OK)
        case "Sleeping":
            return JSONResponse(content={"status": "healthy", "active": False, "label": "💤 Sleeping", "time": server_time, "next": cron_next}, status_code=status.HTTP_200_OK)
        case "Failed":
            return JSONResponse(content={"status": "unhealthy", "active": None, "label": "🔥 Failure", "time": server_time, "next": cron_next}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JSONResponse(content={"status": "unhealthy", "active": None, "label": "❓ Unknown", "time": server_time, "next": cron_next}, status_code=status.HTTP_200_OK)
