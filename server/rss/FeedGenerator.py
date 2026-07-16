from pathlib import Path
import re
from typing import Any, Optional
from dataclasses import dataclass, fields

# Import classes
from server.rss.ArrClient import ArrType
from server.utils.feedconfig import FeedConfig, FeedFilter, FilterApp, FilterTags, FilterWeights
from server.utils.timeformatter import IsoTimeFormatter

@dataclass
class FeedGenerator:
    _default_category: str = "SD"
    _default_remove_jackett_tags: bool = True

    def __init__(self, feed_config: Optional[FeedConfig] = None):
        self._feed_config = feed_config if feed_config else FeedConfig()

    @property
    def Config(self) -> FeedFilter:
        return self._feed_config.config

    @property
    def File(self) -> Path:
        return self.Config.file

    @property
    def PublishPath(self) -> Path: return self._feed_config.path

    @property
    def Tags(self) -> FilterTags | None:
        return self.Config.tags if self.Config else None

    def App(self, server_type: ArrType) -> FilterApp | None: 
        match server_type:
            case ArrType.Radarr:
                filter_type = 'Movies'
            case ArrType.Sonarr:
                filter_type = 'TV'
            case _:
                raise ValueError(f"Unknown library type: {server_type}")
        return getattr(self.Config, filter_type) if self.Config is not None else None
    
    def get_default_unknown_runtime(self, server_type: ArrType) -> int:
        return {ArrType.Radarr: 100, ArrType.Sonarr: 20}.get(server_type)

    def get_tracker_tag(self, tracker_name: str) -> str:
        """Get the tag for a specific tracker name"""
        return self.Tags.tracker_tags.get(tracker_name) if self.Tags and self.Tags.tracker_tags else None

    # -----------------------------
    # Optimizer
    # -----------------------------
    def optimize_results(self, results: list[dict[str, Any]], server_type: ArrType, request_obj: Any) -> list[dict[str, Any]]:
        TAGS = self.Tags
        APP = self.App(server_type=server_type)
        WEIGHTS = APP.weights if APP else FilterWeights()
        REQUIRED_KEYS = ["tags", "category", "lastAdded", "jackett"]

        # Calculate max seeders and runtime for size heuristics
        max_seeders = max((r.get("nbSeeders", 0) for r in results), default=0) or 1
        runtime_default = APP.unknown_runtime if APP else self.get_default_unknown_runtime(server_type=server_type)
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
            source_tag = self.get_tracker_tag(engine)
            if engine == "jackett" and file_name.startswith("["):
                jackett_match = re.search(r'^\[([^\]]+)\] ', file_name)
                if jackett_match:
                    jackett_tag = jackett_match.group(1)
                    source_tag = self.get_tracker_tag(jackett_tag)
                    if TAGS.remove_jackett_tags if TAGS else self._default_remove_jackett_tags:
                        r["fileName"] = file_name[jackett_match.end():]
                        r["jackett"] = jackett_tag
            r["tracker_tag"] = source_tag # Tags for filtering
            r["tags"] = source_tag or '' # Tags for feed
            r["lastAdded"] = IsoTimeFormatter().to_string()
            r["file_size_MB"] = float(r.get("fileSize", 0) or 1) / (1024 ** 2) # Convert to megabytes
            r["file_mbps"] = (r["file_size_MB"] * 8) / (runtime * 60) # Convert file size MB to Mb and runtime minutes to seconds
            r["seeders_10pct"] = r.get("nbSeeders", 0) >= (0.1 * max_seeders)
            r["seeders_50pct"] = r.get("nbSeeders", 0) >= (0.5 * max_seeders)
            r["quality"] = any(q in file_name for q in APP.quality_search) if APP and APP.quality_search else None
            r["favorite"] = r.get("siteUrl") in APP.favorite_sites if APP and APP.favorite_sites else None
            # Size heuristics
            r["size_required"] = (APP.required_mbps.lower or 0) <= r.get("file_mbps", 0) <= (APP.required_mbps.upper or float("inf")) if APP and APP.required_mbps else None
            r["size_preferred"] = (APP.best_mbps.lower or 0) <= r.get("file_mbps", 0) <= (APP.best_mbps.upper or float("inf")) if APP and APP.best_mbps else None
            # Categories: [('WEB-DL', 0), ('SD', 3.33), ('HD', 5.33), ('UHD', 8)]
            tiers = [(k, v) for d in APP.category for k, v in d.items()] if APP and APP.category else [(self._default_category, 0)]
            r["category"] = self._default_category
            for label, threshold in sorted(tiers, key=lambda x: x[1] or 0):
                if threshold is None or r["file_mbps"] >= threshold:
                    r["category"] = label
            # Score
            score = 0
            for field in fields(WEIGHTS):
                if r.get(field.name):
                    value = getattr(WEIGHTS, field.name)
                    score += value if value is not None else 0
            r["score"] = score

        # Filter and sort
        filtered = results
        if TAGS and TAGS.tracker_tags_only:
            filtered = [r for r in filtered if r.get("tracker_tag") is not None]
        elif TAGS and TAGS.tracker_tags_skip:
            filtered = [r for r in filtered if r.get("tracker_tag") is None]
        if WEIGHTS and WEIGHTS.min_score:
            filtered = [r for r in filtered if r.get("score", 0.0) >= WEIGHTS.min_score]
        if APP and APP.required_mbps:
            filtered = [r for r in filtered if r.get("size_required")]
        filtered.sort(key=lambda r: (r.get("score", 0.0), r.get("pubDate") or ""), reverse=True)
        # Drop calc fields that should not persist
        for r in filtered:
            for k in list(r.keys()):
                if k not in REQUIRED_KEYS:
                    r.pop(k, None)
        return filtered
