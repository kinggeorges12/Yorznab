# app.py
import uvicorn
import os
from dotenv import load_dotenv

# Set Docker environment variables in compose file
not_docker_env = os.getenv("DOCKER_ENV") is None
if not_docker_env:
    load_dotenv()

def start():
    """Entry point for the 'start' command."""
    
    # Run uvicorn with your settings
    uvicorn.run(
        "server.run:app",
        host="0.0.0.0",
        port=os.getenv("PORT", 9116),
        reload=not_docker_env
    )