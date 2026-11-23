#!/usr/bin/env python3
"""
Download the photos of a WordPress export: every post's featured photo and
the ones in its text, in the sizes WordPress already made of each, beside
the import's results (backend/data/imports/<file name>/images/, which git
ignores, like the rest of an import).

    python3 scripts/wordpress_images.py ~/Descargas/<site>.WordPress.<date>.xml
    python3 scripts/wordpress_images.py export.xml --sizes medium_large,thumbnail   # what the universe shows
    python3 scripts/wordpress_images.py export.xml --featured-only
    python3 scripts/wordpress_images.py export.xml --statuses publish,private

Asked for on 2026-11-20: the import kept the posts' text and nothing of
their photos, though every published post has one. The export itself holds
no image, only where each is on the site: an attachment's url, its alt
text, caption and sizes (backend/src/services/imports/wordpress.py reads
them, and this script reads the export with that same module).

Sizes, by WordPress's names: `full` (the original, 615 KB at the median
on 2026-11-03, mostly PNG), `medium_large` (768 px wide, 186 of the 187
featured photos) and `thumbnail` (150 x 150, all of them); a size a photo
does not have is skipped, not made. All three by default.

What it leaves, in --out:

- one file per photo and size, `<attachment id>-<size>.<ext>` (a photo
  with no attachment is named by its address's hash);
- `manifest.json`: per post url, its photos in order (the featured one
  first), each with its alt, caption, dimensions and its files by size,
  and what could not be fetched. The universe's backend serves the files
  from it (MAP_IMAGES_DIR; docs/decisions/news-map.md).

Only from the export's own site: a post that shows a photo from elsewhere
keeps its address in the manifest, not a copy. Run it again to fetch what
is missing; a file already there is kept. Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PARSER = ROOT / "backend" / "src" / "services" / "imports" / "wordpress.py"

SIZES = ("full", "medium_large", "thumbnail")

# What a photo may be. Not SVG: it is a document that can carry a script.
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".avif"}

# The largest original of 2026-11-03 is 2.3 MB.
MAX_BYTES = 25 * 1024 * 1024

# A generic name: nothing about who runs it.
USER_AGENT = "Mozilla/5.0 (compatible; wordpress-images/1.0)"


def load_parser():
    """The backend's export reader, by path: it is standard library only, and this script stays so too."""

    spec = importlib.util.spec_from_file_location("wordpress_export", PARSER)
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks the module up by name while it is being defined.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def extension(url: str) -> str:
    return Path(urlsplit(url).path).suffix.lower()


def file_name(image: dict, size: str, url: str) -> str:

    key = str(image["attachment_id"]) if image.get("attachment_id") is not None else hashlib.sha1(image["url"].encode()).hexdigest()[:12]

    return f"{key}-{size}{extension(url)}"


def size_url(image: dict, size: str) -> str | None:

    if size == "full":
        return image["url"]

    found = (image.get("sizes") or {}).get(size)

    return found["url"] if found else None


def address(url: str) -> str:
    """
    The url as a request line can carry it: a file name WordPress kept as
    uploaded ("¡Un-Entrenamiento-Hoy-....png", "9_2024_©Isabelle-Pateer_...jpg"
    on 2026-11-03) percent-encoded, and one already encoded left as it is.
    """

    parts = urlsplit(url)

    return parts._replace(path=quote(parts.path, safe="/%:@!$&'()*+,;=-._~")).geturl()


def fetch(url: str, target: Path, timeout: float) -> int:
    """Download `url` to `target` through a temporary file; the bytes written. Raises on anything but an image."""

    request = urllib.request.Request(address(url), headers={"User-Agent": USER_AGENT, "Accept": "image/*"})

    with urllib.request.urlopen(request, timeout=timeout) as answer:

        kind = answer.headers.get("Content-Type", "")

        if not kind.startswith("image/") or "svg" in kind:
            raise ValueError(f"not a photo ({kind or 'no type'})")

        data = answer.read(MAX_BYTES + 1)

    if len(data) > MAX_BYTES:
        raise ValueError("larger than 25 MB")

    partial = target.with_suffix(target.suffix + ".part")
    partial.write_bytes(data)
    partial.replace(target)

    return len(data)


def main(argv=None) -> int:

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("export", type=Path, help="the WordPress export (.xml)")
    parser.add_argument("--statuses", default="publish", help="which posts: publish (default), private, draft, comma-separated")
    parser.add_argument("--sizes", default=",".join(SIZES), help=f"which sizes, comma-separated, of {', '.join(SIZES)} (default all)")
    parser.add_argument("--featured-only", action="store_true", help="only each post's featured photo")
    parser.add_argument("--workers", type=int, default=4, help="downloads at once (default 4)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", type=Path, help="where (default backend/data/imports/<file name>/images)")
    args = parser.parse_args(argv)

    if not args.export.is_file():
        print(f"No such file: {args.export}", file=sys.stderr)
        return 2

    sizes = [size.strip() for size in args.sizes.split(",") if size.strip()]
    unknown = set(sizes) - set(SIZES)

    if unknown:
        print(f"Unknown size: {', '.join(sorted(unknown))}. Use: {', '.join(SIZES)}.", file=sys.stderr)
        return 2

    wordpress = load_parser()

    try:
        export = wordpress.read(args.export, tuple(s.strip() for s in args.statuses.split(",") if s.strip()))
    except wordpress.NotAnExport as exc:
        print(f"Not an export this can read: {exc}", file=sys.stderr)
        return 2

    own = host_of(export.base_url)
    out = args.out or ROOT / "backend" / "data" / "imports" / args.export.stem / "images"
    out.mkdir(parents=True, exist_ok=True)

    # Every file to fetch, once: a photo two posts show is one download.
    wanted: dict[str, str] = {}
    posts: dict[str, dict] = {}
    elsewhere = 0

    for post in export.posts:

        images = []

        for image in post.images:

            if args.featured_only and not image.get("featured"):
                continue

            files: dict[str, str] = {}

            if host_of(image["url"]) == own:
                for size in sizes:
                    url = size_url(image, size)
                    if url and extension(url) in EXTENSIONS and host_of(url) == own:
                        name = file_name(image, size, url)
                        wanted.setdefault(name, url)
                        files[size] = name
            else:
                elsewhere += 1

            images.append({
                "url": image["url"],
                "featured": bool(image.get("featured")),
                "alt": image.get("alt"),
                "caption": image.get("caption"),
                "width": image.get("width"),
                "height": image.get("height"),
                "sizes": {
                    size: {"width": found["width"], "height": found["height"]}
                    for size, found in (image.get("sizes") or {}).items() if size in files
                },
                "files": files,
            })

        posts[post.url] = {"wp_id": post.wp_id, "title": post.title, "images": images}

    missing = {name: url for name, url in wanted.items() if not (out / name).is_file() or not (out / name).stat().st_size}

    print(f"{len(export.posts)} posts of {export.site}: {sum(len(p['images']) for p in posts.values())} photos, "
          f"{len(wanted)} files in {', '.join(sizes)}; {len(wanted) - len(missing)} already here, {len(missing)} to fetch.")

    failed: dict[str, str] = {}
    fetched = 0
    written = 0
    started = time.perf_counter()

    def one(item: tuple[str, str]) -> tuple[str, int | None, str | None]:
        name, url = item
        try:
            return name, fetch(url, out / name, args.timeout), None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return name, None, str(getattr(exc, "reason", None) or exc)

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            # map keeps the input order, so the progress reads in post order.
            for done, (name, size, error) in enumerate(pool.map(one, sorted(missing.items())), start=1):
                if error:
                    failed[name] = error
                else:
                    fetched += 1
                    written += size or 0
                if done % 25 == 0 or done == len(missing):
                    print(f"  {done}/{len(missing)}  {written / 1e6:.1f} MB  {len(failed)} failed")
    except KeyboardInterrupt:
        print("Stopped; run it again to fetch the rest.", file=sys.stderr)

    # A file that is not there is not in the manifest: the map serves only what it lists.
    for entry in posts.values():
        for image in entry["images"]:
            image["files"] = {size: name for size, name in image["files"].items() if (out / name).is_file()}

    manifest = {
        "export": args.export.name,
        "site": export.base_url,
        "statuses": args.statuses.split(","),
        "sizes": sizes,
        "featuredOnly": args.featured_only,
        "downloadedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {
            "posts": len(posts),
            "photos": sum(len(p["images"]) for p in posts.values()),
            "fromElsewhere": elsewhere,
            "files": sum(1 for name in wanted if (out / name).is_file()),
            "bytes": sum((out / name).stat().st_size for name in wanted if (out / name).is_file()),
            "failed": len(failed),
        },
        "failed": [{"file": name, "url": wanted[name], "error": error} for name, error in sorted(failed.items())],
        "posts": posts,
    }

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = manifest["summary"]
    print(f"Fetched {fetched} files ({written / 1e6:.1f} MB) in {time.perf_counter() - started:.0f} s; "
          f"{summary['files']} of {len(wanted)} here ({summary['bytes'] / 1e6:.0f} MB), {summary['failed']} failed.")
    print(f"Kept in {out}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
