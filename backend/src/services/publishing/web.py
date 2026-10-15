"""
Publishing to the web: this app's own public reader, /reader/stories.

One JSON file per published article under `settings.DRAFTS_PATH /
"published"`, holding a `PublishedStory` snapshot. The public endpoints
read these files and never the draft: a draft goes on changing after it
is published (a background step finishing, a field another stage adds),
and the public page must show exactly what a person approved and
published, until they publish again or take it down.

Beside the drafts, not in the lake: the lake records what the pipeline
found and checked; this is the newsroom's own output. `DraftStore.list`
reads `*.json` in its own directory only, so this subdirectory is never
mistaken for drafts.

Read on every request, without a cache. A newsroom publishes a few
articles a day, each a few KB; the reader's index of the lake exists
because the lake holds thousands of records hundreds of KB each, which
is not this.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
from collections import Counter
from pathlib import Path

from src.models.writer.draft import ArticleDraft, PublishRecord
from src.services.publishing.story import PublishedStory
from src.services.writer.draft_store import now

logger = logging.getLogger(__name__)

STORY_ID = re.compile(r"^[0-9a-f]{16}$")

DEFAULT_PAGE = 20


def public_path(story_id: str) -> str:
    """
    Where the story is read, as a path on this site. A path rather than
    a URL: the backend does not know the address the site is served at
    (a domain, an IAP tunnel, localhost), and the page that links to it
    is always on that same site.
    """

    return f"/reader/stories/{story_id}"


def _same(left: str | None, right: str) -> bool:

    return (left or "").casefold() == right.casefold()


def _facet(values, key: str) -> list[dict]:

    counts = Counter(value for value in values if value)

    return [
        {key: value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


class WebPublisher:

    name = "web"

    label = "Web"

    def __init__(self, root: Path):

        self.root = Path(root)

    def available(self) -> tuple[bool, str | None]:

        return True, None

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def publish(self, draft: ArticleDraft) -> PublishRecord:

        at = now()

        story = PublishedStory.of(draft, published_at=at)

        path = self._path(story.id)

        if path is None:
            raise ValueError(f"Not a story id: {story.id!r}")

        path.parent.mkdir(parents=True, exist_ok=True)

        # Written beside and renamed over, as DraftStore.save does: a
        # crash mid-write leaves the previous snapshot or none, never half
        # a page. The temporary name is unique and does not end in .json,
        # so a reader listing the directory never picks it up.
        temporary = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
        temporary.write_text(
            json.dumps(story.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)

        return PublishRecord(channel=self.name, at=at, url=public_path(story.id))

    def unpublish(self, draft: ArticleDraft) -> None:

        self.remove(draft.id)

    def remove(self, story_id: str) -> bool:
        """Delete the snapshot. False when there was none."""

        path = self._path(story_id)

        if path is None or not path.exists():
            return False

        path.unlink(missing_ok=True)

        return True

    # ------------------------------------------------------------------
    # Reading - the public endpoints
    # ------------------------------------------------------------------

    def _path(self, story_id: str) -> Path | None:

        # The id reaches here from a public URL: never let it name
        # another file.
        if not STORY_ID.fullmatch(story_id or ""):
            return None

        return self.root / f"{story_id}.json"

    def _read(self, path: Path) -> PublishedStory | None:

        try:
            return PublishedStory.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            # Unpublished between the listing and the read.
            return None
        except (OSError, ValueError) as exc:
            # One unreadable file must not take the others off the page.
            logger.warning("Skipping unreadable published story %s: %s", path.name, exc)
            return None

    def story(self, story_id: str) -> dict | None:
        """One published story, as the public page shows it, or None."""

        path = self._path(story_id)

        if path is None or not path.exists():
            return None

        story = self._read(path)

        return story.model_dump(mode="json", by_alias=True) if story else None

    def all(self) -> list[PublishedStory]:
        """Every published story, newest first."""

        if not self.root.exists():
            return []

        stories = [story for story in map(self._read, self.root.glob("*.json")) if story]

        # One format for every stamp (draft_store.now(): UTC, seconds), so
        # the strings sort as the times do. The id breaks a tie, so the
        # order - and so the paging - is stable.
        return sorted(stories, key=lambda story: (story.published_at, story.id), reverse=True)

    def stories(
        self,
        topic: str | None = None,
        language: str | None = None,
        offset: int = 0,
        limit: int = DEFAULT_PAGE,
    ) -> dict:
        """
        The public list, shaped like /reader/articles: a page of cards,
        the total under the filters, and facet counts - each counted
        under the *other* filter, so a chip says what clicking it shows.
        """

        published = self.all()

        in_language = [story for story in published if not language or _same(story.language, language)]

        on_topic = [story for story in published if not topic or _same(story.metadata.topic, topic)]

        selected = [story for story in in_language if not topic or _same(story.metadata.topic, topic)]

        return {
            "total": len(selected),
            "offset": offset,
            "limit": limit,
            "items": [
                story.card().model_dump(mode="json", by_alias=True)
                for story in selected[offset:offset + limit]
            ],
            "topics": _facet((story.metadata.topic for story in in_language), "topic"),
            "languages": _facet((story.language for story in on_topic), "language"),
            "published": len(published),
        }
