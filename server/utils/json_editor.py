import json
import types

from dataclasses import MISSING, asdict, fields, is_dataclass
from typing import (
    Any,
    Dict,
    List,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from dacite import from_dict


class JSONEditor:
    """Convert dataclasses to JSON Editor compatible format."""

    DEFAULT_DESCRIPTIONS = {
        "remove_jackett_tags": "Remove Jackett-specific tags from results",
        "tracker_tags_only": "Only use tracker tags, ignore other tags",
        "tracker_tags_skip": "Skip results that have tracker tags",
        "tracker_tags": "Custom tracker tag mappings (key: tracker, value: tag)",
        "min_score": "Minimum score threshold (0-10). Higher = better quality",
        "seeders_10pct": "Weight multiplier for content with 10% seeders ratio",
        "seeders_50pct": "Weight multiplier for content with 50% seeders ratio",
        "size_preferred": "Preferred file size in GB (higher weight = prefer this size)",
        "favorite": "Weight multiplier for favorite content",
        "quality": "Quality preference weight (higher = prefer better quality)",
        "category": "Category filters",
        "weights": "Weight multipliers for scoring",
        "unknown_runtime": "Default runtime when unknown (in minutes)",
        "quality_search": "Quality search terms",
        "favorite_sites": "Favorite sites",
        "required_mbps": "Minimum required Mbps per quality level",
        "best_mbps": "Best Mbps values per quality level",
        "file": "Optional: Path to the feed source file",
        "tags": "Tag filtering and processing configuration",
        "Movies": "Movie-specific filtering configuration",
        "TV": "TV-specific filtering configuration",
        "lower": "Lower bound value",
        "upper": "Upper bound value",
    }

    UNION_TYPES = (Union, types.UnionType)

    def __init__(
        self,
        obj: Any,
        descriptions: dict | None = None,
    ):
        self.obj = obj
        self.descriptions = {
            **self.DEFAULT_DESCRIPTIONS,
            **(descriptions or {}),
        }

    def to_dict(self) -> dict:
        return asdict(self.obj)

    def to_schema(self) -> dict:
        schema = self._generate_schema(type(self.obj))

        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            **schema,
        }

    def get_editor_config(self) -> dict:
        return {
            "schema": self.to_schema(),
            "data": self.to_dict(),
        }

    def config_json(self, indent: int = 2) -> str:
        return json.dumps(
            self.get_editor_config(),
            indent=indent,
            default=self._json_default,
        )

    def _json_default(self, obj: Any) -> Any:
        if is_dataclass(obj):
            return asdict(obj)

        raise TypeError(
            f"Object of type {type(obj)} is not JSON serializable"
        )

    def _unwrap_optional(
        self,
        annotation: Any,
    ) -> tuple[Any, bool]:
        """
        Return the underlying type and whether it accepts None.

        Examples:
            str              -> (str, False)
            Optional[str]    -> (str, True)
            str | None       -> (str, True)
        """
        origin = get_origin(annotation)

        if origin in self.UNION_TYPES:
            args = get_args(annotation)

            non_none = tuple(
                arg
                for arg in args
                if arg is not type(None)
            )

            is_optional = len(non_none) != len(args)

            if is_optional and len(non_none) == 1:
                return non_none[0], True

        return annotation, False

    def _is_optional(self, annotation: Any) -> bool:
        _, is_optional = self._unwrap_optional(annotation)
        return is_optional

    def _is_dataclass_annotation(
        self,
        annotation: Any,
    ) -> bool:
        annotation, _ = self._unwrap_optional(annotation)
        return is_dataclass(annotation)

    def _generate_schema(self, data_class: Any) -> dict:
        """Generate JSON Schema from a dataclass type."""
        if not is_dataclass(data_class):
            return {"type": "object"}

        properties = {}
        required = []

        # Resolve forward references and postponed annotations.
        type_hints = get_type_hints(data_class)

        for field in fields(data_class):
            field_type = type_hints.get(
                field.name,
                field.type,
            )

            field_schema = self._schema_for_type(field_type)

            field_schema["title"] = (
                field.name
                .replace("_", " ")
                .title()
            )

            field_schema["description"] = (
                self.get_description(field.name)
            )

            properties[field.name] = field_schema

            # Required is determined by whether the dataclass
            # field has a default/default_factory.
            if (
                field.default is MISSING
                and field.default_factory is MISSING
            ):
                required.append(field.name)

        schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        return schema

    def _schema_for_type(self, annotation: Any) -> dict:
        """Generate a JSON Schema fragment for an annotation."""
        annotation, is_optional = self._unwrap_optional(
            annotation
        )

        origin = get_origin(annotation)

        # Dataclass
        if is_dataclass(annotation):
            schema = self._generate_schema(annotation)

        # List[T]
        elif origin in (list, List):
            args = get_args(annotation)

            item_type = (
                args[0]
                if args
                else Any
            )

            schema = {
                "type": "array",
                "items": self._schema_for_type(item_type),
            }

        # Dict[K, V]
        elif origin in (dict, Dict):
            args = get_args(annotation)

            value_type = (
                args[1]
                if len(args) > 1
                else Any
            )

            schema = {
                "type": "object",
                "additionalProperties": (
                    True
                    if value_type is Any
                    else self._schema_for_type(value_type)
                ),
            }

        # Union[A, B]
        elif origin in self.UNION_TYPES:
            schema = {
                "anyOf": [
                    self._schema_for_type(arg)
                    for arg in get_args(annotation)
                ]
            }

        # Any
        elif annotation is Any:
            schema = {}

        # Primitive
        else:
            schema = {
                "type": self._get_json_type_name(annotation)
            }

        if is_optional:
            schema = self._make_nullable(schema)

        return schema

    def _make_nullable(self, schema: dict) -> dict:
        """Allow null for a JSON Schema fragment."""
        schema_type = schema.get("type")

        if schema_type is None:
            return {
                "anyOf": [
                    schema,
                    {"type": "null"},
                ]
            }

        if isinstance(schema_type, list):
            if "null" not in schema_type:
                schema["type"] = [
                    *schema_type,
                    "null",
                ]

            return schema

        schema["type"] = [
            schema_type,
            "null",
        ]

        return schema

    def _get_json_type_name(self, annotation: Any) -> str:
        """Get JSON Schema type name from annotation."""
        annotation, _ = self._unwrap_optional(annotation)

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            type(None): "null",
        }

        if annotation in type_map:
            return type_map[annotation]

        if is_dataclass(annotation):
            return "object"

        origin = get_origin(annotation)

        if origin in (list, List):
            return "array"

        if origin in (dict, Dict):
            return "object"

        return "string"

    def get_description(self, field_name: str) -> str:
        return self.descriptions.get(
            field_name,
            f"Configure {field_name}",
        )

    @classmethod
    def from_dict(
        cls,
        data: dict,
        data_class: Any,
    ) -> Any:
        return from_dict(
            data_class=data_class,
            data=data,
        )