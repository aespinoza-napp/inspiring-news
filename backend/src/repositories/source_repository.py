from logging import getLogger
from pathlib import Path

import yaml

from src.models.core.source import NewsSource

logger = getLogger(__name__)


class SourceRepository:

    def __init__(
        self,
        sources_path: str = "data/sources",
    ):
        self.sources_path = Path(sources_path)

    def list(self) -> list[NewsSource]:

        sources = []

        for file in self.sources_path.glob("*.yaml"):

            # Explicit: the default is the platform's encoding, which on
            # Windows turned "El País" into "El PaÃ­s" on every page.
            with open(file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            sources.append(
                NewsSource(**data)
            )

        # The path is relative to the working directory, and a glob over a
        # missing directory is just empty. That is how the Docker backend
        # ran with no sources at all - nothing failed, /sources simply
        # listed nothing - so say so instead of returning [] quietly.
        if not sources:
            logger.warning(
                "No source YAMLs found in %s (resolved to %s)",
                self.sources_path,
                self.sources_path.resolve(),
            )

        return sources

    def get(
        self,
        source_id: str,
    ) -> NewsSource | None:

        path = self.sources_path / f"{source_id}.yaml"

        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return NewsSource(**data)