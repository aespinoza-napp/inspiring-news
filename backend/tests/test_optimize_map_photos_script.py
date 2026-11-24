"""
scripts/optimize_map_photos.py: the import's photos copied as WebP in the
sizes the universe shows them at, listed in the same manifest, the PNGs
left as they were (2026-11-23).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "optimize_map_photos.py"

_spec = importlib.util.spec_from_file_location("optimize_map_photos", SCRIPT)
optimize = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = optimize
_spec.loader.exec_module(optimize)

POST = "https://inspiringnews.ai/medio-ambiente/lobos/"


def folder_with(tmp_path: Path, files: dict[str, tuple[int, int]], listed: dict[str, str]) -> Path:
    folder = tmp_path / "images"
    folder.mkdir()
    for name, size in files.items():
        Image.new("RGB", size, (40, 120, 90)).save(folder / name)
    manifest = {"site": "https://inspiringnews.ai", "posts": {POST: {"images": [{"featured": True, "files": listed}]}}}
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


def listed_files(folder: Path) -> dict[str, str]:
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["posts"][POST]["images"][0]["files"]


def test_every_size_is_made_from_the_largest_original_and_listed(tmp_path):

    folder = folder_with(
        tmp_path,
        {"7345-full.png": (2400, 1350), "7345-medium_large.png": (768, 432), "7345-thumbnail.png": (150, 150)},
        {"full": "7345-full.png", "medium_large": "7345-medium_large.png", "thumbnail": "7345-thumbnail.png"},
    )

    assert optimize.main([str(folder)]) == 0

    files = listed_files(folder)
    assert files["full"] == "7345-full.png"
    widths = {size: Image.open(folder / files[size]).size for size in optimize.SIZES}
    assert widths == {"thumbnail_webp": (150, 150), "small_webp": (480, 270),
                      "medium_large_webp": (768, 432), "full_webp": (1600, 900)}
    assert all(Image.open(folder / files[size]).format == "WEBP" for size in optimize.SIZES)
    assert json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["site"] == "https://inspiringnews.ai"


def test_a_photo_with_only_its_original_gets_a_square_thumbnail_and_no_enlargement(tmp_path):

    folder = folder_with(tmp_path, {"5814-full.png": (600, 400)}, {"full": "5814-full.png"})

    assert optimize.main([str(folder)]) == 0

    files = listed_files(folder)
    assert Image.open(folder / files["thumbnail_webp"]).size == (150, 150)
    assert Image.open(folder / files["medium_large_webp"]).size == (600, 400)


def test_a_copy_already_made_is_kept(tmp_path):

    folder = folder_with(tmp_path, {"7345-full.png": (900, 600)}, {"full": "7345-full.png"})
    optimize.main([str(folder)])
    made = (folder / "7345-small.webp").stat().st_mtime_ns

    assert optimize.main([str(folder)]) == 0
    assert (folder / "7345-small.webp").stat().st_mtime_ns == made
