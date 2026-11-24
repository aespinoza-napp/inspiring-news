"""
Copies of the photos of the stories a person and the AI chose.

Asked for on 2026-11-24, with the comparison of the person's five against
the AI's (docs/decisions/selection.md, "The person against the AI"): a
round should show what was chosen, pictures included, long after the
outlets have moved or deleted them. Every candidate already carries the
feed's picture as a link (`image`, rss.entry_image); only the chosen ones
- at most five a side - are copied, next to the round's own file:
`lake/stats/selection/photos/<roundId>/<name>`. The rest stay links.

What may be stored is decided by the bytes, not the server: a JPEG, PNG,
GIF, WebP or AVIF by its first bytes, 5 MB at most. SVG is not an image
here (it can carry script). Every hop goes through the URL guard, as a
page fetch does (scraper/fetcher.py). A photo that cannot be had is
recorded with why, never retried on its own, and never fails the round.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests

from src.services.concurrency import bounded_map
from src.services.scraper.fetcher import USER_AGENT
from src.services.scraper.url_guard import BlockedURL, check_url

MAX_BYTES = 5 * 1024 * 1024

# Seconds per request, and for the whole batch: a person waits on it when
# their choice is recorded, and one slow host must not hold them.
TIMEOUT = 10
BUDGET = 20

# At most ten photos a round, from as many outlets: one request each.
CONCURRENCY = 5

MAX_REDIRECTS = 5

# What a kept photo's file is called, and served as (GET
# /ingest/rounds/{id}/photos/{name}).
MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
}

NAME = re.compile(r"^[0-9a-f]{16}\.(?:jpg|png|gif|webp|avif)$")


class NotAPhoto(Exception):
    pass


def kind_of(data: bytes) -> str | None:
    """The extension the bytes say they are, or None for anything else."""

    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    if data.startswith((b"GIF87a", b"GIF89a")):
        return "gif"

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"

    if data[4:12] in (b"ftypavif", b"ftypavis"):
        return "avif"

    return None


def name_for(image: str, extension: str) -> str:
    """A photo's file name: its link's hash, so the same picture is one file."""

    return f"{hashlib.sha256(image.encode('utf-8')).hexdigest()[:16]}.{extension}"


def download(url: str) -> bytes:
    """
    The bytes at `url`, at most MAX_BYTES, every redirect re-checked by
    the guard. Raises BlockedURL, NotAPhoto, and requests' own errors.
    """

    for _ in range(MAX_REDIRECTS + 1):

        response = requests.get(
            check_url(url),
            timeout=TIMEOUT,
            allow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "image/*"},
            stream=True,
        )

        if response.is_redirect:
            response.close()
            url = requests.compat.urljoin(url, response.headers["location"])
            continue

        try:
            response.raise_for_status()

            length = response.headers.get("content-length") or ""

            if length.isdigit() and int(length) > MAX_BYTES:
                raise NotAPhoto(f"larger than {MAX_BYTES // (1024 * 1024)} MB")

            data = bytearray()

            for chunk in response.iter_content(64 * 1024):
                data += chunk
                if len(data) > MAX_BYTES:
                    raise NotAPhoto(f"larger than {MAX_BYTES // (1024 * 1024)} MB")

            return bytes(data)

        finally:
            response.close()

    raise BlockedURL(f"Too many redirects starting at {url!r}.")


class PhotoKeeper:

    def __init__(self, fetch: Callable[[str], bytes] = download):
        self.fetch = fetch

    def keep(self, folder: Path, candidates: list[dict]) -> dict[str, dict]:
        """
        {candidate url: what became of its photo}: `file`, `contentType` and
        `bytes` when kept, `error` when not, `image` (the link) either way.
        Candidates without an `image` are not asked for.
        """

        todo = [candidate for candidate in candidates if candidate.get("image")]

        if not todo:
            return {}

        def one(candidate: dict) -> tuple[str, dict]:

            image = candidate["image"]

            try:
                data = self.fetch(image)
            except Exception as exc:
                return candidate["url"], {"image": image, "error": _why(exc)}

            extension = kind_of(data)

            if extension is None:
                return candidate["url"], {"image": image, "error": "not a JPEG, PNG, GIF, WebP or AVIF image"}

            name = name_for(image, extension)

            try:
                folder.mkdir(parents=True, exist_ok=True)
                temporary = folder / f"{name}.tmp"
                temporary.write_bytes(data)
                os.replace(temporary, folder / name)
            except OSError as exc:
                return candidate["url"], {"image": image, "error": _why(exc)}

            return candidate["url"], {
                "image": image,
                "file": name,
                "contentType": MEDIA_TYPES[extension],
                "bytes": len(data),
                "keptAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }

        def late(candidate: dict) -> tuple[str, dict]:
            return candidate["url"], {"image": candidate["image"], "error": f"no answer within {BUDGET} s"}

        return dict(bounded_map(
            one,
            todo,
            max_workers=min(CONCURRENCY, len(todo)),
            thread_name_prefix="photos",
            timeout=BUDGET,
            late=late,
        ))


def _why(exc: Exception) -> str:
    """One line for the round's record: the kind of failure and its message, cut."""

    text = f"{type(exc).__name__}: {exc}" if not isinstance(exc, NotAPhoto) else str(exc)

    return text[:200]
