from pathlib import Path

import yaml

from src.models.source import NewsSource


class SourceRepository:

    def __init__(
        self,
        sources_path: str = "data/sources",
    ):
        self.sources_path = Path(sources_path)

    def list(self) -> list[NewsSource]:

        sources = []

        for file in self.sources_path.glob("*.yaml"):

            with open(file) as f:
                data = yaml.safe_load(f)

            sources.append(
                NewsSource(**data)
            )

        return sources

    def get(
        self,
        source_id: str,
    ) -> NewsSource | None:

        path = self.sources_path / f"{source_id}.yaml"

        if not path.exists():
            return None

        with open(path) as f:
            data = yaml.safe_load(f)

        return NewsSource(**data)