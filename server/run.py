from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from contextlib import asynccontextmanager

# Start cron job first
import server.cron.rssrefresh

# Import routers after cron
from server.routers import status, torznab, webhook
from server.web.routers import web_routers
from server.routers.handler import RouteHandler

# Import docs
from server.utils.docs import create_openapi, project_info

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    try:
        # Start RSS refresh cron job in daemon mode
        asyncio.create_task(server.cron.rssrefresh.main(["--daemon"]))
        print("🚀 Background RSS refresh cron job started")
    except Exception as e:
        print(f"❌ Failed to start RSS refresh cron job: {e}")
    
    yield
    
    # Shutdown
    print("🛑 Application shutting down")

app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(status.router)
app.include_router(torznab.router)
app.include_router(webhook.router)
app.include_router(web_routers)

# Mount default routes for API to v1
@app.api_route(RouteHandler.API, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def redirect_to_v1(request: Request):
    url = request.url
    new_path = f"{RouteHandler.INDEXER}"
    return RedirectResponse(url=url.replace(path=new_path), status_code=307)

@app.api_route(RouteHandler.API + "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def redirect_to_v1(path: str, request: Request):
    url = request.url
    new_path = f"{RouteHandler.API_v1}/{path}"
    return RedirectResponse(url=url.replace(path=new_path), status_code=307)

# Setup docs
app.openapi_schema = create_openapi(app)

# Mount static directory
app.mount(RouteHandler.STATIC, StaticFiles(directory=RouteHandler.STATIC_DIR), name="static")

# Favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(RouteHandler.get_static_dir("favicon.ico"))
