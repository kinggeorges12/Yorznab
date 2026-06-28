from fastapi import APIRouter
from fastapi.responses import JSONResponse

# Import local modules
from server.routers.handler import RouteHandler
from server.utils.settings import AppSettings

router = APIRouter()

# Docker status check
@router.get(RouteHandler.STATUS)
async def status():
    return JSONResponse(content={"status": "healthy"}, status_code=200)
