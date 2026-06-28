import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import asyncio
from contextlib import asynccontextmanager

# Start cron job first
import cron.rssrefresh

# Import routers after cron
from routers import login, status, torznab, webhook
from server.routers.handler import RouteHandler

# Set static directory handling
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    try:
        # Start RSS refresh cron job in daemon mode
        asyncio.create_task(cron.rssrefresh.main(["--daemon"]))
        print("🚀 Background RSS refresh cron job started")
    except Exception as e:
        print(f"❌ Failed to start RSS refresh cron job: {e}")
    
    yield
    
    # Shutdown
    print("🛑 Application shutting down")

app = FastAPI(lifespan=lifespan)

# Include routers
app.include_router(login.router)
app.include_router(status.router)
app.include_router(torznab.router)
app.include_router(webhook.router)

# Mount static directory
app.mount(RouteHandler.STATIC, StaticFiles(directory=STATIC_DIR), name="static")

# Favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(STATIC_DIR + "/favicon.ico")

# Default route - redirects root to /login
@app.get("/")
async def root():
    return RedirectResponse(url="/login", status_code=302)

