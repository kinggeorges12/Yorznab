from dataclasses import is_dataclass, fields
from typing import Any, Optional, Type, Dict, get_origin, get_args, Union, List
import json


class Guifier:
    """Convert dataclasses to Guifier-compatible JSON format with type validation"""
    
    # Default descriptions for common field names
    DEFAULT_DESCRIPTIONS = {
        # FilterTags fields
        "remove_jackett_tags": "Remove Jackett-specific tags from results",
        "tracker_tags_only": "Only use tracker tags, ignore other tags",
        "tracker_tags_skip": "Skip results that have tracker tags",
        "tracker_tags": "Custom tracker tag mappings (key: tracker, value: tag)",
        
        # FilterWeights fields
        "min_score": "Minimum score threshold (0-10). Higher = better quality",
        "seeders_10pct": "Weight multiplier for content with 10% seeders ratio",
        "seeders_50pct": "Weight multiplier for content with 50% seeders ratio",
        "size_preferred": "Preferred file size in GB (higher weight = prefer this size)",
        "favorite": "Weight multiplier for favorite content",
        "quality": "Quality preference weight (higher = prefer better quality)",
        
        # FilterApp fields
        "category": "Category filters (e.g., ['action', 'comedy'])",
        "weights": "Weight multipliers for scoring",
        "unknown_runtime": "Default runtime when unknown (in minutes)",
        "quality_search": "Quality search terms (e.g., ['1080p', '4K'])",
        "favorite_sites": "Favorite sites (prioritize results from these)",
        "required_mbps": "Minimum required Mbps per quality level",
        "best_mbps": "Best Mbps values per quality level",
        
        # FeedFilter fields
        "file": "Optional: Path to the feed source file",
        "tags": "Tag filtering and processing configuration",
        "Movies": "Movie-specific filtering configuration",
        "TV": "TV-specific filtering configuration",
    }
    
    # Default value for each type (used when creating new fields)
    DEFAULT_VALUES = {
        "string": "",
        "number": 0.0,
        "integer": 0,
        "boolean": False,
        "object": {},
        "array": [],
        "null": None
    }
    
    def __init__(self, obj: Any, skip_none: bool = False, descriptions: Optional[dict] = None):
        """
        Initialize Guifier converter
        
        Args:
            obj: The dataclass instance to convert
            skip_none: If True, skip None values
            descriptions: Custom descriptions to override defaults
        """
        self.obj = obj
        self.skip_none = skip_none
        self.descriptions = {**self.DEFAULT_DESCRIPTIONS, **(descriptions or {})}
    
    def get_description(self, field_name: str) -> str:
        """Get description for a field"""
        return self.descriptions.get(field_name, f"Configure {field_name}")
    
    def get_field_type(self, value: Any) -> str:
        """Get the value type string for Guifier"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        if is_dataclass(value):
            return "object"
        return "string"
    
    def get_guifier_field_type(self, value: Any) -> str:
        """Get the field type for Guifier UI"""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        if isinstance(value, str):
            return "text"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        if is_dataclass(value):
            return "object"
        return "text"
    
    def get_default_value(self, field_type: str) -> Any:
        """Get default value for a field type"""
        return self.DEFAULT_VALUES.get(field_type)
    
    def to_dict(self, include_null: bool = True) -> dict:
        """Convert dataclass to Guifier-compatible dict"""
        return self._wrap_for_guifier(self.obj, include_null)
    
    def to_json(self, include_null: bool = True, indent: int = 2) -> str:
        """Convert dataclass to Guifier-compatible JSON string"""
        return json.dumps(self.to_dict(include_null), indent=indent)
    
    def __str__(self) -> str:
        return self.to_json()
    
    def _get_field_type_from_annotation(self, annotation: Any) -> str:
        """Extract the actual type from a field annotation"""
        origin = get_origin(annotation)
        if origin is Optional:
            args = get_args(annotation)
            if args:
                annotation = args[0]
        
        if origin is Union:
            args = get_args(annotation)
            for arg in args:
                if arg in (float, int):
                    return "number"
        
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        
        if annotation in type_map:
            return type_map[annotation]
        
        if hasattr(annotation, "__name__"):
            name = annotation.__name__.lower()
            if name in type_map.values():
                return name
            if name == "float":
                return "number"
            if name == "int":
                return "integer"
        
        return "string"
    
    def _dataclass_to_guifier(self, obj: Any, include_null: bool = True, parent_key: str = None, parent_path: List[str] = None) -> dict:
        """
        Recursively convert a dataclass to Guifier-compatible dict.
        Matches the style from the example with _path, _key, _value, _valueType, _fieldType.
        """
        if obj is None:
            return {}
        
        if parent_path is None:
            parent_path = []
        
        if is_dataclass(obj):
            result = {}
            for field in fields(obj):
                value = getattr(obj, field.name)
                field_type = self._get_field_type_from_annotation(field.type)
                current_path = parent_path + [field.name]
                
                if value is None:
                    if include_null and not self.skip_none:
                        result[field.name] = {
                            "_path": ["root"] + current_path,
                            "_key": field.name,
                            "_value": None,
                            "_valueType": "null",
                            "_fieldType": "null",
                            "_params": {
                                "description": self.get_description(field.name)
                            }
                        }
                    continue
                
                if is_dataclass(value):
                    result[field.name] = {
                        "_path": ["root"] + current_path,
                        "_key": field.name,
                        "_value": self._dataclass_to_guifier(value, include_null, field.name, current_path),
                        "_valueType": "object",
                        "_fieldType": "object",
                        "_params": {
                            "description": self.get_description(field.name)
                        }
                    }
                elif isinstance(value, list):
                    # Check if it's a list of dataclasses
                    if value and is_dataclass(value[0]):
                        array_items = []
                        for idx, item in enumerate(value):
                            item_path = current_path + [idx]
                            array_items.append({
                                "_path": ["root"] + item_path,
                                "_key": idx,
                                "_value": self._dataclass_to_guifier(item, include_null, field.name, item_path),
                                "_valueType": "object",
                                "_fieldType": "object"
                            })
                        result[field.name] = {
                            "_path": ["root"] + current_path,
                            "_key": field.name,
                            "_value": array_items,
                            "_valueType": "array",
                            "_fieldType": "array",
                            "_params": {
                                "description": self.get_description(field.name)
                            }
                        }
                    else:
                        # List of primitives
                        result[field.name] = {
                            "_path": ["root"] + current_path,
                            "_key": field.name,
                            "_value": value,
                            "_valueType": "array",
                            "_fieldType": "array",
                            "_params": {
                                "description": self.get_description(field.name)
                            }
                        }
                else:
                    result[field.name] = {
                        "_path": ["root"] + current_path,
                        "_key": field.name,
                        "_value": value,
                        "_valueType": self.get_field_type(value),
                        "_fieldType": self.get_guifier_field_type(value),
                        "_params": {
                            "description": self.get_description(field.name)
                        }
                    }
            
            return result
        
        return {}
    
    def _wrap_for_guifier(self, obj: Any, include_null: bool = True) -> dict:
        """Wrap a dataclass in the full Guifier metadata structure"""
        if not obj or not is_dataclass(obj):
            return {}
        
        result = {}
        for field in fields(obj):
            value = getattr(obj, field.name)
            current_path = [field.name]
            
            if value is None:
                if include_null and not self.skip_none:
                    result[field.name] = {
                        "_path": ["root"] + current_path,
                        "_key": field.name,
                        "_value": None,
                        "_valueType": "null",
                        "_fieldType": "null",
                        "_params": {
                            "description": self.get_description(field.name)
                        }
                    }
                continue
            
            if is_dataclass(value):
                result[field.name] = {
                    "_path": ["root"] + current_path,
                    "_key": field.name,
                    "_value": self._dataclass_to_guifier(value, include_null, field.name, current_path),
                    "_valueType": "object",
                    "_fieldType": "object",
                    "_params": {
                        "description": self.get_description(field.name)
                    }
                }
            elif isinstance(value, list):
                # Check if it's a list of dataclasses
                if value and is_dataclass(value[0]):
                    array_items = []
                    for idx, item in enumerate(value):
                        item_path = current_path + [idx]
                        array_items.append({
                            "_path": ["root"] + item_path,
                            "_key": idx,
                            "_value": self._dataclass_to_guifier(item, include_null, field.name, item_path),
                            "_valueType": "object",
                            "_fieldType": "object"
                        })
                    result[field.name] = {
                        "_path": ["root"] + current_path,
                        "_key": field.name,
                        "_value": array_items,
                        "_valueType": "array",
                        "_fieldType": "array",
                        "_params": {
                            "description": self.get_description(field.name)
                        }
                    }
                else:
                    # List of primitives
                    result[field.name] = {
                        "_path": ["root"] + current_path,
                        "_key": field.name,
                        "_value": value,
                        "_valueType": "array",
                        "_fieldType": "array",
                        "_params": {
                            "description": self.get_description(field.name)
                        }
                    }
            else:
                result[field.name] = {
                    "_path": ["root"] + current_path,
                    "_key": field.name,
                    "_value": value,
                    "_valueType": self.get_field_type(value),
                    "_fieldType": self.get_guifier_field_type(value),
                    "_params": {
                        "description": self.get_description(field.name)
                    }
                }
        
        return result