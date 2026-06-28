from dataclasses import asdict, dataclass, field, fields
import os
import re
from typing import Any, Optional
from dacite import from_dict

# Import classes
from server.rss.ArrClient import ArrType
from server.utils.config import ConfigFile
from server.utils.settings import AppSettings
from server.utils.timeformatter import IsoTimeFormatter

@dataclass
class FilterWeights:
    min_score: Optional[float] = None
    seeders_10pct: Optional[float] = None
    seeders_50pct: Optional[float] = None
    size_preferred: Optional[float] = None
    favorite: Optional[float] = None
    quality: Optional[float] = None

@dataclass
class FilterApp:
    category: Optional[list[dict[str, Optional[float]]]] = field(default_factory=list)
    weights: Optional[FilterWeights] = field(default_factory=FilterWeights)
    unknown_runtime: Optional[int] = None
    quality_search: Optional[list[str]] = field(default_factory=list)
    favorite_sites: Optional[list[str]] = field(default_factory=list)
    required_mbps: Optional[dict[str, float]] = field(default_factory=dict)
    best_mbps: Optional[dict[str, float]] = field(default_factory=dict)

@dataclass
class FilterTags:
    remove_jackett_tags: Optional[bool] = None
    tracker_tags_only: Optional[bool] = None
    tracker_tags: Optional[dict[str, str]] = field(default_factory=dict)

@dataclass
class FilterConfig:
    tags: Optional[FilterTags] = field(default_factory=FilterTags)
    Movies: Optional[FilterApp] = field(default_factory=FilterApp)
    TV: Optional[FilterApp] = field(default_factory=FilterApp)

@dataclass
class QBitFilter:
    _config: FilterConfig = field(default_factory=FilterConfig)
    _config_file = "filters.yaml"
    _default_category: str = "SD"

    def __init__(self):
        filter_file = ConfigFile(os.getenv("SEARCH_FILTER", self._config_file))
        # Resolve config file filters.yaml
        if filter_file.exists:
            config_raw = AppSettings(self._config_file).get()
            self._config = from_dict(data_class=FilterConfig, data=config_raw)
            self._config.Movies.unknown_runtime = 100 if self._config.Movies.unknown_runtime is None else self._config.Movies.unknown_runtime
            self._config.TV.unknown_runtime = 20 if self._config.TV.unknown_runtime is None else self._config.TV.unknown_runtime

    @property
    def Config(self) -> FilterConfig: return self._config
    
    @property
    def Tags(self) -> FilterTags | None:
        return self._config.tags

    def App(self, server_type: ArrType) -> FilterApp | None: 
        match server_type:
            case ArrType.Radarr:
                filter_type = 'Movies'
            case ArrType.Sonarr:
                filter_type = 'TV'
            case _:
                raise ValueError(f"Unknown library type: {server_type}")
        return getattr(self.Config, filter_type)
    
    def get_tracker_tag(self, tracker_name: str) -> str:
        """Get the tag for a specific tracker name"""
        return self.Tags.tracker_tags.get(tracker_name, "")

    # -----------------------------
    # Optimizer
    # -----------------------------
    def optimize_results(self, results: list[dict[str, Any]], server_type: ArrType, request_obj: Any) -> list[dict[str, Any]]:
        TAGS = self.Tags
        APP = self.App(server_type=server_type)
        WEIGHTS = APP.weights
        REQUIRED_KEYS = ["tags", "category", "lastAdded", "jackett"]

        # Calculate max seeders and runtime for size heuristics
        max_seeders = max((r.get("nbSeeders", 0) for r in results), default=0) or 1
        runtime_default = APP.unknown_runtime
        # Check for series request
        if isinstance(request_obj, list):
            # TV runtime: sum of runtime of episodes in request_obj list
            runtime = sum((ep.get("runtime") or runtime_default) for ep in request_obj)
        else:
            runtime = (request_obj or {}).get("runtime") or runtime_default

        # Adjust Jackett names and private tracker tags
        for r in results:
            for key in r.keys():
                if key not in REQUIRED_KEYS:
                    REQUIRED_KEYS.append(key)
            engine = r.get("engineName")
            file_name = r.get("fileName", "")
            tags = self.get_tracker_tag(engine)
            if engine == "jackett" and file_name.startswith("["):
                jackett_match = re.search(r'^\[([^\]]+)\] ', file_name)
                if jackett_match:
                    jackett_tag = jackett_match.group(1)
                    tags = self.get_tracker_tag(jackett_tag)
                    if TAGS.remove_jackett_tags:
                        r["fileName"] = file_name[jackett_match.end():]
                        r["jackett"] = jackett_tag
            r["tags"] = tags
            r["lastAdded"] = IsoTimeFormatter().to_string()
            r["file_size_MB"] = float(r.get("fileSize", 0) or 1) / (1024 ** 2)
            r["file_mbps"] = (r["file_size_MB"] / 8) * (runtime / 60) # Convert MB to Mb and minutes to seconds
            r["seeders_10pct"] = r.get("nbSeeders", 0) >= (0.1 * max_seeders)
            r["seeders_50pct"] = r.get("nbSeeders", 0) >= (0.5 * max_seeders)
            r["quality"] = any(q in file_name for q in APP.quality_search)
            r["favorite"] = r.get("siteUrl") in APP.favorite_sites
            # Size heuristics
            r["size_required"] = APP.required_mbps.get("lower", 0) <= r.get("file_mbps", 0) <= APP.required_mbps.get("upper", float("inf"))
            r["size_preferred"] = APP.best_mbps.get("lower", 0) <= r.get("file_mbps", 0) <= APP.best_mbps.get("upper", float("inf"))
            # Categories
            tiers = [(k, v) for d in APP.category for k, v in d.items()]
            r["category"] = self._default_category
            for label, threshold in sorted(tiers, key=lambda x: x[1] or 0):
                if threshold is None or r["file_mbps"] >= threshold:
                    r["category"] = label
            # Score
            score = 0
            for field in fields(WEIGHTS):
                if r.get(field.name):
                    score += getattr(WEIGHTS, field.name)
            r["score"] = score

        # Filter and sort
        filtered = results
        if TAGS.tracker_tags_only:
            filtered = [r for r in filtered if r.get("tags")]
        if WEIGHTS.min_score and APP.required_mbps:
            filtered = [r for r in filtered if r.get("score", 0.0) >= WEIGHTS.min_score and r.get("size_required")]
        filtered.sort(key=lambda r: (r.get("score", 0.0), r.get("pubDate") or ""), reverse=True)
        # Drop calc fields that should not persist
        for r in filtered:
            for k in list(r.keys()):
                if k not in REQUIRED_KEYS:
                    r.pop(k, None)
        return filtered
