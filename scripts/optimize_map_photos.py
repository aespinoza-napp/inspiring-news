#!/usr/bin/env python3
"""
Make light copies of the import's photos for the universe: WebP, in the four
sizes it shows them at, beside the PNGs scripts/wordpress_images.py
downloaded, and listed in the same manifest.json.

Asked for on 2026-11-23: the universe was slow to load "because of the
photos". They are the site's own files, mostly PNG: the 768 px one weighed
212 KB at the median and up to 702 KB, and the card that shows on hover
asked for it on every story the pointer crossed. As WebP:

    thumbnail_webp     150 x 150, as WordPress cut it    the photos in space, lists
    small_webp         480 px wide                       the hover card, the selected photo in space
    medium_large_webp  768 px wide                       the story's panel
    full_webp          at most 1600 px wide              the photo opened large

The map prefers them and falls back to the PNGs for a photo that has none
(backend/src/services/news_map/graph_source.py, served_photo), so running
this is optional and never breaks a photo. Run it again after
wordpress_images.py, which writes the manifest anew: a copy already made is
kept unless its source is newer.

    cd backend && uv run python ../scripts/optimize_map_photos.py \\
        data/imports/inspiringnews-buenasnoticias.WordPress.2026-11-03/images

Pillow, from the backend's environment (the packages already need it).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageOps

# size name -> (largest width, or None for WordPress's own crop; WebP quality)
SIZES = {
    "thumbnail_webp": (None, 70),
    "small_webp": (480, 72),
    "medium_large_webp": (768, 75),
    "full_webp": (1600, 80),
}

# Where each copy is made from, best first: the largest original there is,
# so a copy is never an enlargement of a smaller one; the thumbnail from
# WordPress's own 150 x 150 crop when the photo has one.
SOURCES = {
    "thumbnail_webp": ("thumbnail", "full", "large", "medium_large"),
    "small_webp": ("full", "large", "medium_large"),
    "medium_large_webp": ("full", "large", "medium_large"),
    "full_webp": ("full", "large", "medium_large"),
}

THUMBNAIL = (150, 150)

# The manifest's file names: "<attachment id>-<size>.<ext>", nothing with a path in it.
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


def copy_name(source: str, size: str) -> str:
    """'2808-full.png' -> '2808-small.webp': the attachment's id, the copy's size."""

    stem = source.split("-", 1)[0]
    return f"{stem}-{size.removesuffix('_webp')}.webp"


def make(folder: Path, source: str, size: str) -> tuple[str, int] | None:
    """One copy, or None when the source cannot be read. (its name, its bytes)."""

    width, quality = SIZES[size]
    name = copy_name(source, size)
    target = folder / name
    origin = folder / source

    if target.is_file() and target.stat().st_mtime >= origin.stat().st_mtime:
        return name, target.stat().st_size

    try:
        with Image.open(origin) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")

            if width is None:
                # A thumbnail made from a larger photo: WordPress's square, centred crop.
                if image.size != THUMBNAIL:
                    image = ImageOps.fit(image, THUMBNAIL, Image.Resampling.LANCZOS)
            elif image.width > width:
                image = image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)

            partial = target.with_suffix(".webp.part")
            image.save(partial, "WEBP", quality=quality, method=4)
            os.replace(partial, target)
    except (OSError, ValueError) as error:
        print(f"  {source}: {error}", file=sys.stderr)
        return None

    return name, target.stat().st_size


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path, help="the images folder, with its manifest.json")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    manifest_path = args.folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    jobs: list[tuple[dict, str, str]] = []

    for entry in (manifest.get("posts") or {}).values():
        for photo in (entry or {}).get("images") or []:
            files = photo.get("files") or {}
            for size, preferred in SOURCES.items():
                source = next((files[s] for s in preferred if isinstance(files.get(s), str) and SAFE_NAME.match(files[s])
                               and (args.folder / files[s]).is_file()), None)
                if source:
                    jobs.append((photo, size, source))

    started = time.monotonic()
    before = after = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        made = list(pool.map(lambda job: make(args.folder, job[2], job[1]), jobs))

    for (photo, size, source), result in zip(jobs, made):
        if result is None:
            continue
        name, weight = result
        photo["files"][size] = name
        if size in ("medium_large_webp", "thumbnail_webp"):
            plain = photo["files"].get(size.removesuffix("_webp"))
            if plain and (args.folder / plain).is_file():
                before += (args.folder / plain).stat().st_size
                after += weight

    manifest["webp"] = {"sizes": {size: {"width": w, "quality": q} for size, (w, q) in SIZES.items()},
                        "madeAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    partial = manifest_path.with_suffix(".json.part")
    partial.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(partial, manifest_path)

    done = sum(1 for result in made if result)
    print(f"{done} of {len(jobs)} copies in {time.monotonic() - started:.0f} s; "
          f"the 768 px and thumbnail sizes {before / 1e6:.1f} MB as PNG, {after / 1e6:.1f} MB as WebP")
    return 0 if done == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
