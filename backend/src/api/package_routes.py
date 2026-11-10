"""
Ready-to-post packages of a draft (src/services/packages/,
docs/decisions/writing.md, "Packages"). Registered in main.py, behind the
API key like everything under /drafts.

- GET  /drafts/{id}/packages                    every package, newest first, and the channels
- POST /drafts/{id}/packages                    build one: {"channels": [...]}, all four by default
- GET  /drafts/{id}/packages/{pid}              its manifest
- GET  /drafts/{id}/packages/{pid}/zip          everything in it, with the manifest
- GET  /drafts/{id}/packages/{pid}/files/{path} one file the manifest names
- POST /drafts/{id}/packages/{pid}/wordpress    send its post to the configured site, as a draft

Building is synchronous: a package is a dozen PNGs and two text files,
a second or two; a video adds a few seconds when ffmpeg is there. It
reads the draft under no lock and writes nothing to it, so it cannot
interleave with a review; it refuses a busy draft all the same.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from src.api.routes import require_storage_key
from src.container import get_draft_store, get_package_builder
from src.models.writer.package import CHANNELS, Channel
from src.services.packages import video, wordpress
from src.services.packages.content import content_hash
from src.services.packages.builder import NotPackageable, PackageNotFound

router = APIRouter(prefix="/drafts", dependencies=[Depends(require_storage_key)])

ID_PATTERN = r"^[0-9a-f]{16}$"

MEDIA_TYPES = {
    ".png": "image/png",
    ".mp4": "video/mp4",
    ".json": "application/json",
    ".xml": "application/xml",
    ".txt": "text/plain; charset=utf-8",
}

CHANNEL_LABELS = {
    "wordpress": "WordPress",
    "instagram": "Instagram carousel",
    "stories": "Stories",
    "tiktok": "TikTok",
}


class NewPackageRequest(BaseModel):

    channels: list[Channel] = Field(default_factory=lambda: list(CHANNELS), min_length=1, max_length=4)


def _draft(draft_id: str):

    draft = get_draft_store().get(draft_id)

    if draft is None:
        raise HTTPException(status_code=404, detail="No draft with this id.")

    return draft


def _dump(manifest) -> dict:

    return manifest.model_dump(mode="json", by_alias=True)


def channels() -> list[dict]:
    """The four channels, and what each can do here and now."""

    return [
        {
            "name": "wordpress",
            "label": CHANNEL_LABELS["wordpress"],
            "canSend": wordpress.configured(),
            "note": None if wordpress.configured() else "Files only: set WORDPRESS_URL, WORDPRESS_USER and WORDPRESS_APP_PASSWORD to send a draft to the site.",
        },
        {"name": "instagram", "label": CHANNEL_LABELS["instagram"], "canSend": False,
         "note": "Files to post by hand: Instagram's API needs an approved Meta app."},
        {"name": "stories", "label": CHANNEL_LABELS["stories"], "canSend": False,
         "note": "Files to post by hand, with the link sticker."},
        {"name": "tiktok", "label": CHANNEL_LABELS["tiktok"], "canSend": False,
         "note": ("A photo post and a video" if video.available() else "A photo post; no video without ffmpeg")
                 + ", posted by hand: TikTok's API needs an approved, audited app."},
    ]


@router.get("/{draft_id}/packages")
def list_packages(draft_id: str = Path(pattern=ID_PATTERN)):

    draft = _draft(draft_id)

    return {
        "packages": [_dump(manifest) for manifest in get_package_builder().list(draft_id)],
        "channels": channels(),
        # Which text the draft holds now: a package whose contentHash
        # differs was made from an earlier one.
        "currentContentHash": content_hash(draft),
    }


@router.post("/{draft_id}/packages", status_code=201)
def create_package(request: NewPackageRequest | None = None, draft_id: str = Path(pattern=ID_PATTERN)):

    draft = _draft(draft_id)

    try:
        manifest = get_package_builder().build(draft, list((request or NewPackageRequest()).channels))
    except NotPackageable as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return _dump(manifest)


@router.get("/{draft_id}/packages/{package_id}")
def get_package(draft_id: str = Path(pattern=ID_PATTERN), package_id: str = Path(pattern=ID_PATTERN)):

    try:
        return _dump(get_package_builder().get(draft_id, package_id))
    except PackageNotFound:
        raise HTTPException(status_code=404, detail="No package with this id.")


@router.get("/{draft_id}/packages/{package_id}/zip")
def download_package(draft_id: str = Path(pattern=ID_PATTERN), package_id: str = Path(pattern=ID_PATTERN)):

    try:
        data = get_package_builder().zip(draft_id, package_id)
    except PackageNotFound:
        raise HTTPException(status_code=404, detail="No package with this id.")

    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="package-{draft_id}-{package_id}.zip"'},
    )


@router.get("/{draft_id}/packages/{package_id}/files/{path:path}")
def package_file(path: str, draft_id: str = Path(pattern=ID_PATTERN), package_id: str = Path(pattern=ID_PATTERN)):

    try:
        target, entry = get_package_builder().file(draft_id, package_id, path)
    except PackageNotFound:
        raise HTTPException(status_code=404, detail="No such file in this package.")

    return FileResponse(target, media_type=MEDIA_TYPES.get(target.suffix, "application/octet-stream"))


@router.post("/{draft_id}/packages/{package_id}/wordpress")
def send_to_wordpress(draft_id: str = Path(pattern=ID_PATTERN), package_id: str = Path(pattern=ID_PATTERN)):
    """
    The package's post created on the configured site as a draft. 409 when
    the site is not configured, the package has no WordPress files or was
    sent already (a second send would make a second post); 502 when the
    site refuses.
    """

    builder = get_package_builder()

    try:
        manifest = builder.get(draft_id, package_id)
    except PackageNotFound:
        raise HTTPException(status_code=404, detail="No package with this id.")

    package = next((channel for channel in manifest.channels if channel.channel == "wordpress"), None)

    if package is None:
        raise HTTPException(status_code=409, detail="This package has no WordPress files: build one with the wordpress channel.")

    if package.delivery is not None:
        raise HTTPException(status_code=409, detail=f"Already sent as post {package.delivery.post_id}.")

    if not wordpress.configured():
        raise HTTPException(status_code=409, detail="Set WORDPRESS_URL, WORDPRESS_USER and WORDPRESS_APP_PASSWORD in backend/.env first.")

    try:
        delivery = wordpress.send_draft(builder.post_for(draft_id, package_id))
    except wordpress.WordPressRefused as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return _dump(builder.record_delivery(draft_id, package_id, delivery))
