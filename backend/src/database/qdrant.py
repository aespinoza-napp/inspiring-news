from pathlib import Path

from qdrant_client import QdrantClient

from src.config.settings import settings


class QdrantDatabase:


    def __init__(
        self,
        path: str | Path | None = None,
    ):

        storage_path = (
            Path(path)
            if path
            else settings.QDRANT_PATH
        )

        storage_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = QdrantClient(
            path=str(storage_path)
        )


    def close(self):

        self.client.close()