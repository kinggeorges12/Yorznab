import os
import json
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath
import re

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
import httpx

# Import modules
from server.routers import status
from server.routers.handler import RouteHandler
from server.utils.customlogger import CustomLogger
from server.web.routers.auth import authenticate

LOGGER = CustomLogger(name="CacheRouter")

router = APIRouter(prefix=RouteHandler.STATIC, tags=["web"])

@router.get("/cache/ace/{file_path:path}")
async def get_ace_file(file_path: str):
    # Security: Prevent path traversal attacks
    safe_path = Path(file_path)

    if ".." in safe_path.parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")

    ace_download_path = (
        "https://cdn.jsdelivr.net/npm/"
        "ace-builds@latest/src-min-noconflict"
    )
    local_path = Path("cache/ace")

    return Response(
        media_type = "text/javascript",
        content = download_and_cache(
            f"{ace_download_path}/{file_path}",
            PurePosixPath(local_path, safe_path),
        )
    )

@router.get("/cache/css/{file_path:path}")
async def get_font_file(file_path: str):
    # Security: Prevent path traversal attacks
    safe_path = Path(file_path)

    if ".." in safe_path.parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")

    font_download_path = (
        f"https://fontlibrary.org/face/{safe_path}"
    )
    local_path = Path(f"cache/css/{safe_path}")

    fonts_css = download_and_cache(
            f"{font_download_path}",
            local_path,
        )
    fonts_css = re.sub(r"(src: url\(')/assets/fonts/([^']+'\))", f"\\1{RouteHandler.get_static_url('cache/fonts')}/\\2", fonts_css)
    with open(RouteHandler.get_static_dir(local_path), 'w') as f:
        f.write(fonts_css)

    return Response(
        media_type="text/css",
        content=fonts_css,
    )

@router.get("/cache/fonts/{file_path:path}")
async def get_font_file(file_path: str):
    # Security: Prevent path traversal attacks
    safe_path = PurePosixPath(file_path)

    if ".." in safe_path.parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path")

    font_download_path = (
        f"https://fontlibrary.org/assets/fonts/{safe_path}"
    )
    local_path = PurePosixPath(f"cache/fonts/{safe_path}")

    download_and_cache(
        f"{font_download_path}",
        str(local_path),
        read_mode='rb',
    )

    return FileResponse(
        path=RouteHandler.get_static_dir(local_path),
        media_type='application/font-sfnt'
    )

def fetch_external_file(external_url: str) -> bytes:
    """
    Download a file from external URL and return raw bytes
    """
    with httpx.Client() as client:
        try:
            response = client.get(external_url, follow_redirects=True)
            response.raise_for_status()
            return response.content
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=404, detail=f"External file not found: {e}")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error connecting to external server: {e}")

def download_and_cache(url, file, read_mode='r', cache_duration_hours=None) -> bytes:
    """
    Download a file and cache it locally
    """
    static_file = RouteHandler.get_static_dir(file)
    cache_file = Path(static_file)
    LOGGER.debug(f"Checking cache for file: {cache_file}")
    # Check if cache exists and is fresh
    cache_ready = False
    if os.path.exists(cache_file):
        cache_ready = True
        if cache_duration_hours is not None:
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))
            cache_ready = file_age < timedelta(hours=cache_duration_hours)
    if not cache_ready:
        # Download fresh data
        LOGGER.debug(f"Downloading from: {url}")
        content_bytes = fetch_external_file(url)
        
        # Save to cache
        LOGGER.debug(f"Caching to: {cache_file}")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if content is JSON or binary
        try:
            # Try to parse as JSON
            data = json.loads(content_bytes)
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Save as binary
            with open(cache_file, 'wb') as f:
                f.write(content_bytes)
    with open(cache_file, read_mode) as f:
        LOGGER.debug(f"Loading from cache: {cache_file}")
        return f.read()

    return None
