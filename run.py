import uvicorn
import os
from dotenv import load_dotenv

# Force unbuffered output for Python
os.environ['PYTHONUNBUFFERED'] = '1'

# Set Docker environment variables in compose file
not_docker_env = os.getenv("DOCKER_ENV") is None
if not_docker_env:
    load_dotenv()

def server():
    """Entry point for the 'start' command."""
    
    # Run uvicorn with your settings
    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=os.getenv("PORT", 9116),
        reload=not_docker_env and os.getenv("DEV_MODE", "false").lower() == "true",
    )

if __name__ == "__main__":
    server()