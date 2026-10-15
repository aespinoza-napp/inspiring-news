"""
A channel a finished draft can be published to (docs/decisions/writing.md,
"Publishing"). Today the web - this app's own public reader - is the only
one that does anything; TikTok and Instagram are listed so the interface
has their place, and say why they are not available.

A publisher is told nothing about the draft store or the approval rule:
the routes decide *whether* to publish (an approved draft, an available
channel, nothing busy) and the publisher only does it. That keeps the
rule in one place for every channel, and a channel that later needs
network calls and minutes of rendering changes only its own class (and
moves the route onto `DraftStore.run_in_background`).
"""

from __future__ import annotations

from typing import Protocol

from src.models.writer.draft import ArticleDraft, PublishRecord


class ChannelUnavailable(RuntimeError):
    """Publishing to a channel that cannot take it yet."""

    def __init__(self, channel: str, reason: str):

        super().__init__(f"{channel} is not available: {reason}")

        self.channel = channel
        self.reason = reason


class Publisher(Protocol):

    # What the API and the draft's PublishRecord call the channel.
    name: str

    # What a person reads.
    label: str

    def available(self) -> tuple[bool, str | None]:
        """Whether it can publish now, and if not, why - in a sentence a person can act on."""

    def publish(self, draft: ArticleDraft) -> PublishRecord:
        """Publish `draft` as it is now. Publishing again replaces what was there."""

    def unpublish(self, draft: ArticleDraft) -> None:
        """Take it down. Idempotent: nothing published is not an error."""
