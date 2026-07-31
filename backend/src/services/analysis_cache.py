import hashlib
import json
from pathlib import Path

from src.config.settings import settings


class AnalysisCache:
    """
    Simple URL-keyed file cache for AnalysisService results, so
    re-analyzing the same URL doesn't repeat a real scrape + SearXNG
    search + one LLM call per claim every single time.
    """

    def __init__(self, directory: Path | None = None):

        self.directory = directory or (settings.CACHE_PATH / "analysis")

        self.directory.mkdir(parents=True, exist_ok=True)

    def get(self, url: str) -> dict | None:

        path = self._path(url)

        if not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, url: str, result: dict) -> None:

        self._path(url).write_text(
            json.dumps(result, default=str),
            encoding="utf-8",
        )

    def _path(self, url: str) -> Path:

        key = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()

        return self.directory / f"{key}.json"
