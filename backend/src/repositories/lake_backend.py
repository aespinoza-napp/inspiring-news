from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable, Protocol

from src.models.storage.lineage import DataLayer


class LakeBackend(Protocol):
    """
    Storage interface for the three-layer lake.

    Everything above this line (DataLakeRepository, AnalysisService) deals
    only in records and never in files, so swapping the default
    JSON-on-disk implementation for MongoDB/Postgres/S3 is a matter of
    writing another class with these five methods - no pipeline change.
    Documents are plain JSON-safe dicts for exactly that reason.
    """

    def write(self, layer: DataLayer, record_id: str, document: dict) -> None: ...

    def read(self, layer: DataLayer, record_id: str) -> dict | None: ...

    def list(self, layer: DataLayer, limit: int | None = None) -> list[dict]: ...

    def find_by_article(self, layer: DataLayer, article_id: str) -> list[dict]: ...

    def manifest(self, limit: int | None = None) -> list[dict]: ...


class JsonFileLakeBackend:
    """
    Default backend: one JSON file per record under
    <root>/<layer>/<record_id>.json, plus an append-only audit log at
    <root>/_manifest.jsonl.

    The manifest is the traceability spine. Each line records one write
    (when, which layer, which record, which run, which article, which
    parent record, which content hash), so the full history of the lake
    is readable in file order even if a record is later overwritten by a
    re-run - the records tell you the current state, the manifest tells
    you how it got there.

    Writes are atomic (temp file + os.replace) because the persist stage
    runs inside FastAPI's background threadpool: a reader listing a layer
    while a job writes into it must never observe a half-written file.
    """

    MANIFEST_NAME = "_manifest.jsonl"

    def __init__(self, root: Path):

        self.root = Path(root)

        for layer in DataLayer:
            (self.root / layer.value).mkdir(parents=True, exist_ok=True)

        # Guards manifest appends only. Record writes are already atomic
        # per file and each has a unique name, so they need no lock.
        self._manifest_lock = threading.Lock()

    # ------------------------------------------------------------------

    def _path(self, layer: DataLayer, record_id: str) -> Path:

        return self.root / layer.value / f"{record_id}.json"

    def write(self, layer: DataLayer, record_id: str, document: dict) -> None:

        path = self._path(layer, record_id)

        temporary = path.with_suffix(".json.tmp")

        temporary.write_text(
            json.dumps(document, indent=2, default=str),
            encoding="utf-8",
        )

        os.replace(temporary, path)

        self._append_manifest(layer, record_id, document)

    def read(self, layer: DataLayer, record_id: str) -> dict | None:

        path = self._path(layer, record_id)

        if not path.exists():
            return None

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def list(self, layer: DataLayer, limit: int | None = None) -> list[dict]:

        documents = sorted(
            self._read_all(layer),
            key=lambda document: str(
                document.get("lineage", {}).get("produced_at", "")
            ),
            reverse=True,
        )

        return documents[:limit] if limit else documents

    def find_by_article(self, layer: DataLayer, article_id: str) -> list[dict]:

        return [
            document
            for document in self.list(layer)
            if document.get("lineage", {}).get("article_id") == article_id
        ]

    def manifest(self, limit: int | None = None) -> list[dict]:

        path = self.root / self.MANIFEST_NAME

        if not path.exists():
            return []

        entries = []

        for line in path.read_text(encoding="utf-8").splitlines():

            line = line.strip()

            if not line:
                continue

            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                # A torn final line (process killed mid-append) must not
                # make the whole audit log unreadable.
                continue

        return entries[-limit:] if limit else entries

    # ------------------------------------------------------------------

    def _read_all(self, layer: DataLayer) -> Iterable[dict]:

        for file in (self.root / layer.value).glob("*.json"):

            try:
                yield json.loads(file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

    def _append_manifest(
        self,
        layer: DataLayer,
        record_id: str,
        document: dict,
    ) -> None:

        lineage = document.get("lineage", {})

        entry = {
            "at": datetime.now().isoformat(),
            "layer": layer.value,
            "record_id": record_id,
            "run_id": lineage.get("run_id"),
            "article_id": lineage.get("article_id"),
            "source_url": lineage.get("source_url"),
            "content_hash": lineage.get("content_hash"),
            "parent_layer": lineage.get("parent_layer"),
            "parent_record_id": lineage.get("parent_record_id"),
            "code_revision": lineage.get("code_revision"),
        }

        with self._manifest_lock:

            with (self.root / self.MANIFEST_NAME).open(
                "a",
                encoding="utf-8",
            ) as handle:

                handle.write(json.dumps(entry) + "\n")
