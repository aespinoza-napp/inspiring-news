from __future__ import annotations

from pathlib import Path
from logging import getLogger
from typing import Type, TypeVar

from pydantic import BaseModel

logger = getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LocalRepository:

    def __init__(
        self,
        model: Type[T],
        folder: Path,
    ):

        self.model = model

        self.folder = folder

        self.folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    ########################################################

    def __iter__(self):

        yield from self.list()

    ########################################################

    def _filename(
        self,
        item: T,
    ) -> Path:
        print("item", item)
        print("item.published_at", getattr(item, "published_at", None))
        date = getattr(
            item,
            "published_at",
            None,
        )

        if date is not None:

            date = date.date()

        else:

            date = "unknown"

        source = getattr(
            item,
            "source_id",
            "unknown",
        )

        identifier = getattr(
            item,
            "id",
            "unknown",
        )

        return (
            self.folder
            / f"{date}_{source}_{identifier}.json"
        )

    ########################################################

    def save(
        self,
        item: T,
    ):

        self._filename(item).write_text(
            item.model_dump_json(
                indent=2,
            ),
            encoding="utf-8",
        )

    ########################################################

    def load(
        self,
        item_id: str,
    ) -> T:

        for file in self.folder.glob("*.json"):

            if item_id not in file.name:
                continue

            return self.model.model_validate_json(
                file.read_text(
                    encoding="utf-8",
                )
            )

        raise FileNotFoundError(item_id)

    ########################################################

    def list(self) -> list[T]:

        results = []

        for file in self.folder.glob("*.json"):

            try:

                results.append(

                    self.model.model_validate_json(
                        file.read_text(
                            encoding="utf-8",
                        )
                    )

                )

            except Exception as exc:

                logger.warning(
                    "Cannot read %s (%s)",
                    file,
                    exc,
                )

        if hasattr(self.model, "published_at"):

            try:

                results.sort(
                    key=lambda x: x.published_at,
                    reverse=True,
                )

            except Exception:
                pass

        return results

    ########################################################

    def first(self) -> T | None:

        items = self.list()

        return items[0] if items else None

    ########################################################

    def delete(
        self,
        item_id: str,
    ):

        for file in self.folder.glob("*.json"):

            if item_id in file.name:

                file.unlink()

                return

    ########################################################

    def count(self) -> int:

        return len(
            list(
                self.folder.glob("*.json")
            )
        )