from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from src.models.evaluation.custom_fact import CustomFact


class CustomFactRepository:
    """
    The hand-labelled custom set, one JSON object per line, beside
    x-fact's file in backend/data/evaluation/.

    JSONL rather than the lake because it is a dataset that goes into
    git and into the paper, not pipeline output: one file a reviewer can
    read, diff and load with the same code as xfact_en_es.jsonl. It stays
    small (100-150 rows), so an edit rewrites the whole file - through a
    temporary file and os.replace, so a crash mid-write leaves the old
    file rather than half of a new one.
    """

    def __init__(self, path: Path):

        self.path = Path(path)
        # The form can be open in two tabs; a read-modify-write that
        # interleaves loses a label.
        self._lock = threading.RLock()

    def list(self) -> list[CustomFact]:

        with self._lock:

            if not self.path.exists():
                return []

            with self.path.open(encoding="utf-8") as f:
                return [
                    CustomFact.model_validate_json(line)
                    for line in f
                    if line.strip()
                ]

    def get(self, fact_id: str) -> CustomFact | None:

        return next((f for f in self.list() if f.id == fact_id), None)

    def add(self, fact: CustomFact) -> CustomFact:

        with self._lock:

            self.path.parent.mkdir(parents=True, exist_ok=True)

            with self.path.open("a", encoding="utf-8") as f:
                f.write(_line(fact))

        return fact

    def replace(self, fact: CustomFact) -> CustomFact | None:

        with self._lock:

            facts = self.list()
            index = next((i for i, f in enumerate(facts) if f.id == fact.id), None)

            if index is None:
                return None

            facts[index] = fact
            self._write_all(facts)

        return fact

    def delete(self, fact_id: str) -> bool:

        with self._lock:

            facts = self.list()
            kept = [f for f in facts if f.id != fact_id]

            if len(kept) == len(facts):
                return False

            self._write_all(kept)

        return True

    def _write_all(self, facts: list[CustomFact]) -> None:

        tmp = self.path.with_suffix(self.path.suffix + ".tmp")

        with tmp.open("w", encoding="utf-8") as f:
            for fact in facts:
                f.write(_line(fact))

        os.replace(tmp, self.path)


def _line(fact: CustomFact) -> str:

    # ensure_ascii=False, like prepare_xfact_eval.py: half the set is
    # Spanish, and escaped accents make the file unreadable in a diff.
    return json.dumps(fact.model_dump(mode="json"), ensure_ascii=False) + "\n"
