import time
from pathlib import Path

from qdrant_client import QdrantClient

from src.config.settings import settings


class QdrantDatabase:

    # QdrantClient's local mode takes an exclusive file lock on the
    # storage directory. Under `uvicorn --reload`, the old worker process
    # is killed and a new one spawned on every file change - if the new
    # process tries to open the lock before the old one has fully released
    # it, QdrantClient raises a RuntimeError ("already accessed by another
    # instance"). That's a timing race, not a real conflict, so retry
    # briefly instead of crashing the whole app on every reload.
    LOCK_RETRY_ATTEMPTS = 5
    LOCK_RETRY_DELAY_SECONDS = 0.5

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

        self.client = self._connect(storage_path)

    def _connect(self, storage_path: Path) -> QdrantClient:

        last_error: Exception | None = None

        for attempt in range(self.LOCK_RETRY_ATTEMPTS):

            try:
                return QdrantClient(path=str(storage_path))
            except RuntimeError as exc:
                if "already accessed by another instance" not in str(exc):
                    raise
                last_error = exc
                time.sleep(self.LOCK_RETRY_DELAY_SECONDS)

        raise last_error


    def close(self):

        self.client.close()