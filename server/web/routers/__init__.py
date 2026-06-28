import importlib
import pkgutil
from fastapi import APIRouter
from pathlib import Path

# This will be the main router that includes all sub-routers
web_routers = APIRouter()

# Auto-discover and include all routers in this directory
package_path = Path(__file__).parent

for module_info in pkgutil.iter_modules([str(package_path)]):
    if module_info.name == "__init__":
        continue
    
    # Import the module
    module = importlib.import_module(f".{module_info.name}", package=__package__)
    
    # Find all routers in the module and include them in web_routers
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, APIRouter):
            web_routers.include_router(attr)

# Export the main router
__all__ = ['web_routers']