import hashlib
import json
from pathlib import Path

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds


class AnalysisCache:
    """
    Simple URL-keyed file cache for AnalysisService results, so
    re-analyzing the same URL doesn't repeat a real scrape + SearXNG
    search + one LLM call per claim every single time.

    Entries are stamped with SCHEMA_VERSION and an entry written by an
    older shape is treated as a miss. The cache has no expiry, so
    without this an entry written before a response-shape change would
    be served forever - the frontend would receive a payload missing
    whatever field was added (and keep receiving it, since a hit never
    rewrites the entry). Bump SCHEMA_VERSION whenever the dict returned
    by AnalysisService.analyze() changes shape.
    """

    SCHEMA_VERSION = 2

    def __init__(self, directory: Path | None = None):

        self.directory = directory or (settings.CACHE_PATH / "analysis")

        self.directory.mkdir(parents=True, exist_ok=True)

    def get(
        self,
        url: str,
        thresholds: PipelineThresholds | None = None,
    ) -> dict | None:

        path = self._path(url, thresholds)

        if not path.exists():
            return None

        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        if not isinstance(entry, dict):
            return None

        if entry.get("schemaVersion") != self.SCHEMA_VERSION:
            return None

        return entry.get("result")

    def set(
        self,
        url: str,
        result: dict,
        thresholds: PipelineThresholds | None = None,
    ) -> None:

        self._path(url, thresholds).write_text(
            json.dumps(
                {
                    "schemaVersion": self.SCHEMA_VERSION,
                    "url": url,
                    "result": result,
                },
                default=str,
            ),
            encoding="utf-8",
        )

    def _path(
        self,
        url: str,
        thresholds: PipelineThresholds | None = None,
    ) -> Path:
        """
        The key is the URL *plus* any thresholds that differ from the
        environment defaults. A run with a custom admission threshold is
        a different analysis of the same URL, and must not be served the
        default run's cached answer (nor overwrite it). A default run
        keys on the URL alone, so existing entries stay reachable.
        """

        material = url.strip()

        overridden = (
            thresholds.overridden_from_defaults() if thresholds else {}
        )

        if overridden:
            material += "|" + json.dumps(overridden, sort_keys=True)

        key = hashlib.sha256(material.encode("utf-8")).hexdigest()

        return self.directory / f"{key}.json"
