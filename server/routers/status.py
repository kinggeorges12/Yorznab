from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

# Import local modules
from server.cron.rssrefresh import CronRunner
from server.routers.handler import RouteHandler
from server.utils.timeformatter import TimezoneAware

router = APIRouter(prefix=RouteHandler.STATUS, tags=["system"])

@router.get("")
async def cron_status():
    """
    Get the current status of the RSS refresh cron job.
    
    Returns the cron job status, server time, and next scheduled run time.
    
    Status codes:
    - healthy/active: Cron is running (Initializing, Started, Running)
    - healthy/inactive: Cron is sleeping (Sleeping) 
    - unhealthy: Cron has failed (Failed)
    
    Returns:
        JSONResponse with status, active state, label, current time, and next run time
    """
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
