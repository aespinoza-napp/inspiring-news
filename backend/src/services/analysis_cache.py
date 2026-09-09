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

    SCHEMA_VERSION = 3

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
        The key is the URL plus the run's **effective** threshold values.

        It used to be the URL plus only the thresholds that *differed*
        from the environment defaults, so that a default run kept keying
        on the URL alone and existing entries stayed reachable. That is
        unsound: the deviation is measured against whatever the defaults
        happen to be right now. Change DUPLICATE_THRESHOLD in `.env` from
        0.90 to 0.96 and a default run before and a default run after
        both record "no overrides" and hash to the same key - so the
        second run is served an answer computed under the old threshold,
        with nothing in the response saying so. The schema version does
        not change either, because the response *shape* did not.

        Hashing the effective values closes that. The cost is that an
        env change now invalidates the affected entries, which is the
        correct behaviour and cheap - it is a cache.
        """

        effective = (
            (thresholds or PipelineThresholds()).model_dump()
        )

        material = url.strip() + "|" + json.dumps(effective, sort_keys=True)

        key = hashlib.sha256(material.encode("utf-8")).hexdigest()

        return self.directory / f"{key}.json"
