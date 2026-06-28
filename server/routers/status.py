from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# Docker status check
@router.get("/status")
async def status():
    return JSONResponse(content={"status": "healthy"}, status_code=200)
