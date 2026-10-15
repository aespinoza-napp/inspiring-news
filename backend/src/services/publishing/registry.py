"""
The channels, by name, in the order the publish panel lists them.

The web publisher is kept apart as well as listed: the public reader's
endpoints read its snapshots, and only it has any.
"""

from __future__ import annotations

from typing import Iterable

from src.services.publishing.publisher import Publisher
from src.services.publishing.web import WebPublisher


class Publishers:

    def __init__(self, web: WebPublisher, others: Iterable[Publisher] = ()):

        self.web = web

        self._by_name: dict[str, Publisher] = {web.name: web}

        for publisher in others:
            self._by_name[publisher.name] = publisher

    def get(self, name: str) -> Publisher | None:

        return self._by_name.get(name)

    def all(self) -> list[Publisher]:

        return list(self._by_name.values())

    def channels(self) -> list[dict]:
        """What GET /publishing/channels returns: each channel, and why one is not available."""

        rows = []

        for publisher in self.all():

            available, reason = publisher.available()

            rows.append(
                {
                    "name": publisher.name,
                    "label": publisher.label,
                    "available": available,
                    "reason": None if available else reason,
                }
            )

        return rows
