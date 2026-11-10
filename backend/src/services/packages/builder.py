"""
Ready-to-post packages of a draft, one directory each under
PACKAGES_PATH/<draft id>/<package id>/, with a `manifest.json` naming
every file and what a person still has to do (docs/decisions/writing.md,
"Packages").

- **wordpress**: post.json (REST API) and post.xml (the importer), both
  status draft. Sent to a site only when a person asks and the site's
  keys are set (wordpress.py).
- **instagram**: a carousel of 1080x1350 cards and caption.txt.
- **stories**: 1080x1920 frames, text inside the safe margins, and the
  link for the link sticker.
- **tiktok**: a photo post (1080x1920 photos and caption.txt), and a
  video only when ffmpeg is installed (video.py).

Instagram and TikTok are files posted by hand. Posting through their
APIs needs a developer app each platform has approved (Meta's
instagram_business_content_publish, TikTok's video.publish after its
audit), which this newsroom does not have: services/publishing/social.py
has what each would need. Nothing here calls either.

Only a draft a person has approved (or published) is packaged: a
package is text about to be posted. A draft being written or rewritten
is refused, like every other stage.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import secrets
import zipfile
from pathlib import Path

from PIL import Image

from src.config.settings import settings
from src.models.writer.draft import ArticleDraft
from src.models.writer.package import (
    CHANNELS,
    Channel,
    ChannelPackage,
    PackageFile,
    PackageManifest,
    WordPressDelivery,
)
from src.services.packages import cards, content as package_content, video, wordpress
from src.services.packages.cards import Block
from src.services.writer.draft_store import now

logger = logging.getLogger(__name__)

PACKAGE_ID = re.compile(r"^[0-9a-f]{16}$")

PACKAGEABLE = ("approved", "published")

# Instagram takes up to 20 cards in a carousel, but one read to the end
# is short: the cover, at most six points, the checks and where to read
# on - nine at most.
CAROUSEL_POINTS = 6
STORY_POINTS = 3
TIKTOK_POINTS = 4


class NotPackageable(RuntimeError):
    pass


class PackageNotFound(LookupError):
    pass


class PackageBuilder:

    def __init__(self, root: Path | None = None, site_url: str | None = None):

        self.root = Path(root or settings.PACKAGES_PATH)
        self.site_url = site_url if site_url is not None else settings.PUBLIC_SITE_URL

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def build(self, draft: ArticleDraft, channels: list[Channel] | None = None) -> PackageManifest:

        if draft.busy:
            raise NotPackageable(f"The draft is busy ({draft.busy}); package it when it is done.")

        if draft.status not in PACKAGEABLE:
            raise NotPackageable("Only an approved or published draft is packaged: approve it first.")

        wanted = [channel for channel in CHANNELS if channel in (channels or CHANNELS)]

        if not wanted:
            raise NotPackageable("Choose at least one channel.")

        text = package_content.read(draft, self.site_url)

        package_id = secrets.token_hex(8)
        folder = self.root / draft.id / package_id
        folder.mkdir(parents=True, exist_ok=False)

        manifest = PackageManifest(
            id=package_id,
            draft_id=draft.id,
            created_at=now(),
            language=draft.language,
            edition=text.edition,
            title=text.title,
            content_hash=package_content.content_hash(draft),
            draft_status=draft.status,
            link=text.link,
        )

        if text.link is None:
            manifest.notes.append(
                "No public link: "
                + ("publish the draft first." if draft.status != "published" else "set PUBLIC_SITE_URL in backend/.env.")
                + " Captions and the story's last frame say where it will be instead."
            )

        manifest.notes.append(f"Cards drawn in {cards.font_name()}.")

        builders = {
            "wordpress": self._wordpress,
            "instagram": self._instagram,
            "stories": self._stories,
            "tiktok": self._tiktok,
        }

        for channel in wanted:
            manifest.channels.append(builders[channel](draft, text, folder, manifest))

        self._write(folder, manifest)

        return manifest

    def _wordpress(self, draft, text, folder: Path, manifest: PackageManifest) -> ChannelPackage:

        post = wordpress.post_json(draft, text)

        files = [
            self._add(folder, manifest, "wordpress/post.json", "wordpress", "post-json",
                      json.dumps(post, ensure_ascii=False, indent=2).encode("utf-8")),
            self._add(folder, manifest, "wordpress/post.xml", "wordpress", "post-xml",
                      wordpress.post_xml(draft, text).encode("utf-8")),
        ]

        steps = [
            "post.xml: Tools > Import > WordPress on the site; it arrives as a draft.",
            "post.json is the REST API's body; tags are left out of it (the API wants the site's tag ids) and are in post.xml by name.",
        ]

        if wordpress.configured():
            steps.insert(0, f"Send it as a draft to {settings.WORDPRESS_URL}: nothing is public until someone publishes it there.")
        else:
            steps.insert(0, "Not sent anywhere: set WORDPRESS_URL, WORDPRESS_USER and WORDPRESS_APP_PASSWORD to send it as a draft.")

        return ChannelPackage(channel="wordpress", files=files, link=text.link, steps=steps)

    def _instagram(self, draft, text, folder: Path, manifest: PackageManifest) -> ChannelPackage:

        form = cards.CAROUSEL
        words = text.words
        accent = cards.accent_of(text.edition)

        pages: list[list[Block]] = [[
            Block(text.title, 78, bold=True, gap=40),
            *([Block(text.subtitle, 44, color=cards.MUTED)] if text.subtitle else []),
        ]]

        pages += self._points(text, form, CAROUSEL_POINTS, size=54, accent=accent)

        if text.total_checks:
            pages.append([
                Block(words["checked"], 70, bold=True, color=accent),
                Block(words["checked_line"].format(judged=text.judged, total=text.total_checks), 48),
            ])

        pages.append([
            Block(words["read_more"], 70, bold=True, gap=40),
            Block(words["link_in_bio"] if text.link else words["no_link"], 46, color=accent),
            Block(text.disclosure, 34, color=cards.MUTED),
        ])

        files = self._draw(folder, manifest, "instagram", "card", form, pages, text,
                           footer_first=f"{words['swipe']} →")

        link_line = f"{words['link_in_bio']}: {text.link}" if text.link else words["no_link"]
        caption = package_content.caption(text, 3, link_line)
        files.append(self._add(folder, manifest, "instagram/caption.txt", "instagram", "caption", caption.encode("utf-8")))

        return ChannelPackage(
            channel="instagram",
            files=files,
            caption=caption,
            link=text.link,
            steps=[
                "Post the cards in order as one carousel and paste caption.txt.",
                "Instagram links in a caption are not clickable: put the link in the bio.",
                "Posted by hand: publishing through Instagram's API needs an approved Meta app, which there is not yet.",
            ],
        )

    def _stories(self, draft, text, folder: Path, manifest: PackageManifest) -> ChannelPackage:

        form = cards.STORY
        words = text.words
        accent = cards.accent_of(text.edition)

        pages: list[list[Block]] = [[
            Block(text.title, 80, bold=True, gap=40),
            *([Block(text.subtitle, 46, color=cards.MUTED)] if text.subtitle else []),
        ]]

        pages += self._points(text, form, STORY_POINTS, size=58, accent=accent)

        # The last frame's text sits at the top, so the link sticker has
        # the empty middle of the frame, inside the safe margins.
        pages.append([
            Block(words["read_more"], 74, bold=True, gap=30),
            Block(f"{words['tap_link']} ↓" if text.link else words["no_link"], 50, color=accent),
        ])

        files = self._draw(folder, manifest, "stories", "frame", form, pages, text, last_on_top=True)

        steps = ["Post the frames in order as stories."]

        if text.link:
            steps.append(f"On the last frame, add the link sticker with {text.link} in the empty space under the text.")
        else:
            steps.append("No link sticker yet: the draft has no public link.")

        steps.append("Posted by hand, like the carousel.")

        return ChannelPackage(channel="stories", files=files, link=text.link, steps=steps)

    def _tiktok(self, draft, text, folder: Path, manifest: PackageManifest) -> ChannelPackage:

        form = cards.TIKTOK
        words = text.words
        accent = cards.accent_of(text.edition)

        pages: list[list[Block]] = [[
            Block(text.title, 80, bold=True, gap=40),
            *([Block(text.subtitle, 46, color=cards.MUTED)] if text.subtitle else []),
        ]]

        pages += self._points(text, form, TIKTOK_POINTS, size=56, accent=accent)

        if text.total_checks:
            pages.append([
                Block(words["checked"], 70, bold=True, color=accent),
                Block(words["checked_line"].format(judged=text.judged, total=text.total_checks), 48),
            ])

        pages.append([
            Block(words["read_more"], 70, bold=True, gap=40),
            Block(words["link_in_bio"] if text.link else words["no_link"], 48, color=accent),
            Block(text.disclosure, 34, color=cards.MUTED),
        ])

        files = self._draw(folder, manifest, "tiktok", "frame", form, pages, text)

        link_line = f"{words['link_in_bio']}: {text.link}" if text.link else words["no_link"]
        caption = package_content.caption(text, 2, link_line)
        files.append(self._add(folder, manifest, "tiktok/caption.txt", "tiktok", "caption", caption.encode("utf-8")))

        steps = [
            "Post the photos in order as a photo post and paste caption.txt.",
            "Posted by hand: TikTok's Content Posting API needs an app it has approved for video.publish and audited.",
        ]

        frames = [folder / path for path in files if path.endswith(".png")]
        clip = video.slideshow(frames, folder / "tiktok" / "video.mp4")

        if clip is not None:
            files.append(self._register(folder, manifest, "tiktok/video.mp4", "tiktok", "video", 1080, 1920))
            steps.insert(1, f"Or post video.mp4 instead ({video.SECONDS_PER_FRAME} s a photo, no sound: add one in TikTok).")
        else:
            manifest.notes.append("No TikTok video: ffmpeg is not installed (or failed). The photo post stands.")

        return ChannelPackage(channel="tiktok", files=files, caption=caption, link=text.link, steps=steps)

    # ------------------------------------------------------------------
    # Pieces
    # ------------------------------------------------------------------

    @staticmethod
    def _points(text, form: cards.Format, limit: int, size: int, accent) -> list[list[Block]]:
        """Up to `limit` points as pages, each with who said it; a point that does not fit is skipped."""

        pages = []

        for point in text.points:

            blocks = [Block(point.text, size, gap=40)]

            if point.sources:
                blocks.append(Block(f"{text.words['source']}: {', '.join(point.sources)}", 36, color=accent))

            if cards.fits(blocks, form):
                pages.append(blocks)

            if len(pages) >= limit:
                break

        return pages

    def _draw(self, folder, manifest, channel, kind, form, pages, text, footer_first=None, last_on_top=False) -> list[str]:

        files = []
        count = len(pages)

        for index, blocks in enumerate(pages, start=1):

            image = cards.render(
                blocks,
                form,
                text.edition,
                text.brand,
                footer=footer_first if index == 1 else None,
                position=f"{index}/{count}",
                vertical="top" if (last_on_top and index == count) else "center",
            )

            path = f"{channel}/{kind}-{index:02d}.png"
            cards.save(image, folder / path)
            files.append(self._register(folder, manifest, path, channel, kind, form.width, form.height))

        return files

    def _add(self, folder: Path, manifest: PackageManifest, path: str, channel, kind, data: bytes) -> str:

        target = folder / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

        return self._register(folder, manifest, path, channel, kind)

    @staticmethod
    def _register(folder: Path, manifest: PackageManifest, path: str, channel, kind, width=None, height=None) -> str:

        data = (folder / path).read_bytes()

        manifest.files.append(PackageFile(
            path=path,
            channel=channel,
            kind=kind,
            bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            width=width,
            height=height,
        ))

        return path

    def _write(self, folder: Path, manifest: PackageManifest) -> None:

        (folder / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def _folder(self, draft_id: str, package_id: str) -> Path:

        if not PACKAGE_ID.match(package_id) or not PACKAGE_ID.match(draft_id):
            raise PackageNotFound(package_id)

        folder = self.root / draft_id / package_id

        if not (folder / "manifest.json").is_file():
            raise PackageNotFound(package_id)

        return folder

    def get(self, draft_id: str, package_id: str) -> PackageManifest:

        folder = self._folder(draft_id, package_id)

        return PackageManifest.model_validate_json((folder / "manifest.json").read_text(encoding="utf-8"))

    def list(self, draft_id: str) -> list[PackageManifest]:

        if not PACKAGE_ID.match(draft_id):
            return []

        found = []

        for manifest in (self.root / draft_id).glob("*/manifest.json"):
            try:
                found.append(PackageManifest.model_validate_json(manifest.read_text(encoding="utf-8")))
            except Exception:
                logger.warning("Unreadable package manifest %s", manifest, exc_info=True)

        return sorted(found, key=lambda item: item.created_at, reverse=True)

    def file(self, draft_id: str, package_id: str, path: str) -> tuple[Path, PackageFile]:
        """A file the manifest names, and only one: a path is looked up, never joined blind."""

        manifest = self.get(draft_id, package_id)

        for entry in manifest.files:
            if entry.path == path:
                return self._folder(draft_id, package_id) / entry.path, entry

        raise PackageNotFound(path)

    def zip(self, draft_id: str, package_id: str) -> bytes:

        manifest = self.get(draft_id, package_id)
        folder = self._folder(draft_id, package_id)

        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(folder / "manifest.json", "manifest.json")
            for entry in manifest.files:
                archive.write(folder / entry.path, entry.path)

        return buffer.getvalue()

    def record_delivery(self, draft_id: str, package_id: str, delivery: WordPressDelivery) -> PackageManifest:

        manifest = self.get(draft_id, package_id)

        for channel in manifest.channels:
            if channel.channel == "wordpress":
                channel.delivery = delivery

        self._write(self._folder(draft_id, package_id), manifest)

        return manifest

    def post_for(self, draft_id: str, package_id: str) -> dict:

        path, _ = self.file(draft_id, package_id, "wordpress/post.json")

        return json.loads(path.read_text(encoding="utf-8"))


def image_size(path: Path) -> tuple[int, int]:

    with Image.open(path) as image:
        return image.size
