import tomllib
from fastapi.openapi.utils import get_openapi

def load_app_info():
    """Load FastAPI info from pyproject.toml."""
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        
        project = data.get("project", {})
        fastapi_conf = data.get("tool", {}).get("fastapi", {})
        urls = data.get("project", {}).get("urls", {})
        
        # Get author info
        authors = project.get("authors", [{}])
        first_author = authors[0] if authors else {}
        
        return {
            "title": project.get("name", "FastAPI"),
            "version": fastapi_conf.get("api_version", project.get("version")),
            "description": project.get("description", ""),
            "servers": [
                {
                    "url": "{server}/api/v1",
                    "description": "API Server",
                    "variables": {
                        "server": {
                            "default": "http://localhost:9116",
                            "description": "Server URL"
                        }
                    }
                }
            ],
            "contact": {
                "name": first_author.get("name", ""),
                "email": first_author.get("email", ""),
                "url": urls.get("repository", ""),
            } if authors else {},
            "license_info": {
                "name": project.get("license", {}).get("text", "MIT"),
                "url": urls.get("license", ""),
            } if project.get("license") else {},
            "terms_of_service": urls.get("support", ""),
            "api_prefix": fastapi_conf.get("api_prefix", "/api/v1"),
        }
    except FileNotFoundError:
        return {
            "title": "Yorznab",
            "version": "1.0.0",
            "description": "... a Torznab indexer that's all YORZ",
            "api_prefix": "/api/v1",
        }


# Load config once
project_info = load_app_info()


def create_openapi(app):
    """Create an OpenAPI schema with the API prefix removed from displayed paths."""
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        # Pass all project_info to get_openapi
        openapi_schema = get_openapi(
            routes=app.routes,
            **{k: v for k, v in project_info.items() if k != "api_prefix"}
        )
        
        # Handle API prefix removal
        api_prefix = project_info.get("api_prefix", "/api/v1")
        if api_prefix:
            new_paths = {}
            for path, item in openapi_schema["paths"].items():
                if path.startswith(api_prefix):
                    path = path.removeprefix(api_prefix) or "/"
                new_paths[path] = item
            openapi_schema["paths"] = new_paths
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi