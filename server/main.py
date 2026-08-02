from fastapi import FastAPI, Request, Response, status as http_status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from contextlib import asynccontextmanager
from starsessions import InMemoryStore, SessionAutoloadMiddleware, SessionMiddleware
from datetime import timedelta

# Start cron job first
import server.cron.rssrefresh

# Import routers after cron
from server.routers import status, torznab, webhook
from server.web.routers import web_routers
from server.routers.handler import RouteHandler

# Import docs
from server.utils.docs import create_openapi

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

# Add the middleware with explicit settings
app.add_middleware(SessionAutoloadMiddleware)
app.add_middleware(
    SessionMiddleware,
    store=InMemoryStore(),
    lifetime=int(timedelta(hours=24).total_seconds()),
    rolling=True,
    cookie_name="session",
    cookie_https_only=False,
    cookie_same_site="lax",
)

# Include routers
app.include_router(status.router)
app.include_router(torznab.router)
app.include_router(webhook.router)
app.include_router(web_routers)

# Mount default routes for default route to home
@app.api_route('/', methods=["GET"], include_in_schema=False)
async def redirect_to_home(request: Request):
    url = request.url
    new_path = f"{RouteHandler.HOME}"
    print(f"Redirecting request from {url.path} to v1")
    return RedirectResponse(url=url.replace(path=new_path), status_code=http_status.HTTP_307_TEMPORARY_REDIRECT)

# Mount default routes for API to indexer
@app.api_route(RouteHandler.API, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"], include_in_schema=False)
async def redirect_to_indexer(request: Request):
    url = request.url
    new_path = f"{RouteHandler.INDEXER}"
    print(f"Redirecting request from {url.path} to indexer")
    return RedirectResponse(url=url.replace(path=new_path), status_code=http_status.HTTP_307_TEMPORARY_REDIRECT)

@app.api_route(RouteHandler.API + "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"], include_in_schema=False)
async def redirect_to_v1(path: str, request: Request):
    url = request.url
    print(f"Redirecting request from {url.path} to v1")
    if url.path.startswith(RouteHandler.API_v1): return Response(status_code=http_status.HTTP_404_NOT_FOUND)
    new_path = f"{RouteHandler.API_v1}/{path}"
    return RedirectResponse(url=url.replace(path=new_path), status_code=http_status.HTTP_307_TEMPORARY_REDIRECT)

# Setup docs
app.openapi_schema = create_openapi(app)

# Mount static directory
app.mount(RouteHandler.STATIC, StaticFiles(directory=RouteHandler.STATIC_DIR), name="static")

# Favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(RouteHandler.get_static_dir("favicon.ico"))