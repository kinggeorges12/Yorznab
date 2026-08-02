import tomllib
from fastapi.openapi.utils import get_openapi
FASTAPI_USER = None
FASTAPI_HOST = None

def load_app_info():
    """Load FastAPI info from pyproject.toml."""
    global FASTAPI_USER, FASTAPI_HOST
    try:
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        
        project = data.get("project", {})
        fastapi_conf = data.get("tool", {}).get("fastapi", {})
        urls = data.get("project", {}).get("urls", {})
        FASTAPI_USER = fastapi_conf.get('user')
        FASTAPI_HOST = fastapi_conf.get('host')
        
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
                            "default": FASTAPI_HOST,
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
PROJECT_INFO = load_app_info()


def create_openapi(app):
    """Create an OpenAPI schema with the API prefix removed from displayed paths."""
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        
        # Pass all project info to the constructor, except api_prefix which is handled separately
        openapi_schema = get_openapi(
            routes=app.routes,
            **{k: v for k, v in PROJECT_INFO.items() if k != "api_prefix"}
        )
        
        # Handle API prefix removal
        api_prefix = PROJECT_INFO.get("api_prefix", "/api/v1")
        if api_prefix:
            new_paths = {}
            for path, item in openapi_schema["paths"].items():
                if path.startswith(api_prefix):
                    path = path.removeprefix(api_prefix) or "/"
                new_paths[path] = item
            openapi_schema["paths"] = new_paths
        
        # Remove csrf_token from all schema definitions
        if "components" in openapi_schema and "schemas" in openapi_schema["components"]:
            schemas = openapi_schema["components"]["schemas"]
            
            # Iterate through all schemas
            for schema_name, schema_content in list(schemas.items()):
                # Remove csrf_token from properties if it exists
                if "properties" in schema_content:
                    if "csrf_token" in schema_content["properties"]:
                        del schema_content["properties"]["csrf_token"]
                    
                    # Also clean up required fields if csrf_token was required
                    if "required" in schema_content:
                        if "csrf_token" in schema_content["required"]:
                            schema_content["required"].remove("csrf_token")
                            # Remove required entirely if empty
                            if not schema_content["required"]:
                                del schema_content["required"]
                    
                    # Handle nested schemas (for allOf, anyOf, etc.)
                    # This is useful if you have schemas that reference other schemas
                    for field in ["allOf", "anyOf", "oneOf"]:
                        if field in schema_content:
                            for sub_schema in schema_content[field]:
                                if "$ref" in sub_schema:
                                    # You might want to recursively clean referenced schemas
                                    # but they'll be handled in the main loop
                                    pass
                                
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi