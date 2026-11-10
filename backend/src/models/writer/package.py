"""
A ready-to-post package of a draft (src/services/packages/): what was
made, for which channel, from which text, and what a person still has to
do by hand. The manifest is written beside the files and is what the API
returns.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.models.writer.draft import CamelModel, Language

Channel = Literal["wordpress", "instagram", "stories", "tiktok"]

CHANNELS: tuple[Channel, ...] = ("wordpress", "instagram", "stories", "tiktok")


class PackageFile(CamelModel):

    # Relative to the package's directory, with forward slashes:
    # "instagram/card-01.png".
    path: str

    channel: Channel

    # "post-json", "post-xml", "card", "frame", "caption", "video".
    kind: str

    bytes: int

    sha256: str

    width: int | None = None

    height: int | None = None


class WordPressDelivery(CamelModel):
    """The one time a package went to a WordPress site: always as a draft."""

    post_id: int

    status: str

    # The draft's edit link on the site, when it answered with one.
    link: str | None = None

    sent_at: str


class ChannelPackage(CamelModel):

    channel: Channel

    files: list[str] = Field(default_factory=list)

    # The text to paste with the media (Instagram, TikTok), or None.
    caption: str | None = None

    # The story's link sticker, or the link to put in the bio.
    link: str | None = None

    # What a person does next, in a sentence each: posting by hand, why
    # nothing was sent, a video left out.
    steps: list[str] = Field(default_factory=list)

    # WordPress only: set once the package was sent.
    delivery: WordPressDelivery | None = None


class PackageManifest(CamelModel):

    id: str

    draft_id: str

    created_at: str

    language: Language

    edition: str = "positive"

    title: str

    # sha256 of title, subtitle and body: which text the files were made
    # from, so a package of an edited draft is visibly out of date.
    content_hash: str

    draft_status: str

    # The public page, when the draft is published and PUBLIC_SITE_URL is set.
    link: str | None = None

    channels: list[ChannelPackage] = Field(default_factory=list)

    files: list[PackageFile] = Field(default_factory=list)

    notes: list[str] = Field(default_factory=list)
