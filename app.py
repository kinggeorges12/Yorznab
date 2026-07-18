# app.py
import uvicorn
import os
from dotenv import load_dotenv

# Set Docker environment variables in compose file
if not os.getenv("DOCKER_ENV"):
    load_dotenv()

def start():
    """Entry point for the 'start' command."""
    
    # Run uvicorn with your settings
    uvicorn.run(
        "server.run:app",
        host="0.0.0.0",
        port=9116,
        reload=True
    )