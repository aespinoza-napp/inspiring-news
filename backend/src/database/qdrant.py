# src/database/qdrant.py

from qdrant_client import QdrantClient

from src.config.settings import settings


class QdrantDatabase:

    def __init__(self):

        settings.QDRANT_PATH.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = QdrantClient(
            path=str(settings.QDRANT_PATH)
        )