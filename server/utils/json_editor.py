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
import yaml

from server.utils.config import ConfigFile
from server.utils.feedconfig import FeedFilter


class JsonEditor:
    """Convert dataclasses to JSON Editor compatible format."""

    DEFAULT_DESCRIPTIONS = {
        "remove_jackett_tags": "Remove Jackett tags from titles, move to custom field",
        "tracker_tags_only": "Only save torrents matching tracker_tags entries",
        "tracker_tags_skip": "Skip torrents matching tracker_tags entries (ignored if tracker_tags_only is active)",
        "tracker_tags": "Add qBittorrent tags per tracker. Leave blank for rules-only",
        "min_score": "Minimum score threshold - lower scores are dropped",
        "seeders_10pct": "Weight bonus when seeders are in top 10%",
        "seeders_50pct": "Weight bonus when seeders are in top 50%",
        "size_preferred": "Weight bonus when size is near the average",
        "favorite": "Weight bonus for favorite content",
        "quality": "Weight bonus for quality content",
        "category": "Category filters with mbps per quality level",
        "weights": "Scoring weight multipliers",
        "unknown_runtime": "Default runtime (minutes) when unknown in Jellyseerr",
        "quality_search": "Search terms that trigger quality score",
        "favorite_sites": "List of favorite sites",
        "required_mbps": "Mbps range - drops torrents outside this",
        "best_mbps": "Preferred Mbps range",
        "tags": "Tag filtering and processing",
        "Movies": "Movie-specific filter settings",
        "TV": "TV-specific filter settings",
    }

    @classmethod
    def get_blank(cls) -> str:
        blank_filter = FeedFilter()
        blank_dict = asdict(blank_filter)
        return yaml.safe_dump(blank_dict, sort_keys=False)

    @classmethod
    def get_template(cls) -> str:
        template_content = ''
        template_file = ConfigFile('feed.yaml.sample')
        with open(template_file.path, "r") as file:
            template_content = file.read()
        return template_content

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