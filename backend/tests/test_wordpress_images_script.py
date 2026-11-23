"""
scripts/wordpress_images.py: a WordPress export's photos downloaded beside
the import, with the manifest the universe's backend serves them from. The
network is replaced by a function that writes bytes; what is tested is
which files are asked for, how they are named and what the manifest says.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from tests.services.imports.test_wordpress import METADATA, STORY, attachment, export, item

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "wordpress_images.py"

_spec = importlib.util.spec_from_file_location("wordpress_images", SCRIPT)
images = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = images
_spec.loader.exec_module(images)


def an_export(tmp_path: Path) -> Path:

    body = STORY + """<figure><img src="https://inspiringnews.ai/wp-content/uploads/2025/12/2-3.png" class="wp-image-5814"/>
<figcaption>Participantes del Spogomi 2025.</figcaption></figure>
<figure><img src="https://upload.wikimedia.org/foto.jpg"/></figure>"""

    path = tmp_path / "site.WordPress.2026-11-03.xml"
    path.write_bytes(export(
        attachment(267, "https://inspiringnews.ai//wp-content/uploads/2025/02/tmpnjt92rgc.png", alt="Monos", metadata=METADATA),
        attachment(5814, "https://inspiringnews.ai//wp-content/uploads/2025/12/2-3.png"),
        item(250, "Monos que bromean", body, meta={"_thumbnail_id": "267"}),
    ))

    return path


def fake_fetch(asked: list[str], failing: set[str] = frozenset()):

    def fetch(url: str, target: Path, timeout: float) -> int:
        asked.append(url)
        if url in failing:
            raise ValueError("not a photo (text/html)")
        target.write_bytes(b"\x89PNG" + url.encode())
        return target.stat().st_size

    return fetch


def test_every_photo_in_every_size_it_has_and_a_manifest(tmp_path, monkeypatch):

    asked: list[str] = []
    monkeypatch.setattr(images, "fetch", fake_fetch(asked))
    out = tmp_path / "images"

    assert images.main([str(an_export(tmp_path)), "--out", str(out), "--workers", "1"]) == 0

    # The featured photo in its three sizes, the text's own only as it is
    # (its attachment has no sizes), and nothing from another site.
    assert sorted(asked) == sorted([
        "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc.png",
        "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc-768x439.png",
        "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc-150x150.png",
        "https://inspiringnews.ai/wp-content/uploads/2025/12/2-3.png",
    ])

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    featured, inline, elsewhere = manifest["posts"]["https://inspiringnews.ai/sociedad/p250/"]["images"]

    assert featured["featured"] and featured["alt"] == "Monos"
    assert featured["files"] == {"full": "267-full.png", "medium_large": "267-medium_large.png", "thumbnail": "267-thumbnail.png"}
    assert featured["sizes"]["medium_large"] == {"width": 768, "height": 439}
    assert inline["caption"] == "Participantes del Spogomi 2025." and inline["files"] == {"full": "5814-full.png"}
    # Its address is kept; no copy.
    assert elsewhere["url"] == "https://upload.wikimedia.org/foto.jpg" and elsewhere["files"] == {}
    assert manifest["summary"]["files"] == 4 and manifest["summary"]["fromElsewhere"] == 1
    assert all((out / name).is_file() for name in featured["files"].values())


def test_a_second_run_fetches_only_what_is_missing_and_a_failure_is_not_listed(tmp_path, monkeypatch):

    export_path = an_export(tmp_path)
    out = tmp_path / "images"
    thumbnail = "https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc-150x150.png"

    first: list[str] = []
    monkeypatch.setattr(images, "fetch", fake_fetch(first, failing={thumbnail}))
    assert images.main([str(export_path), "--out", str(out), "--workers", "1"]) == 1

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    featured = manifest["posts"]["https://inspiringnews.ai/sociedad/p250/"]["images"][0]
    # The map serves only what the manifest lists, so a missing file is not in it.
    assert "thumbnail" not in featured["files"]
    assert manifest["failed"] == [{"file": "267-thumbnail.png", "url": thumbnail, "error": "not a photo (text/html)"}]

    second: list[str] = []
    monkeypatch.setattr(images, "fetch", fake_fetch(second))
    assert images.main([str(export_path), "--out", str(out), "--workers", "1"]) == 0
    assert second == [thumbnail]


def test_only_the_sizes_asked_for_and_only_featured_photos(tmp_path, monkeypatch):

    asked: list[str] = []
    monkeypatch.setattr(images, "fetch", fake_fetch(asked))

    assert images.main([str(an_export(tmp_path)), "--out", str(tmp_path / "i"), "--sizes", "thumbnail", "--featured-only"]) == 0

    assert asked == ["https://inspiringnews.ai/wp-content/uploads/2025/02/tmpnjt92rgc-150x150.png"]


def test_an_unknown_size_is_refused(tmp_path):

    assert images.main([str(an_export(tmp_path)), "--sizes", "huge"]) == 2


def test_a_file_name_with_accents_is_asked_for_percent_encoded():
    """Four photos of 2026-11-03 failed with "ordinal not in range(128)" before."""

    assert images.address("https://inspiringnews.ai/wp-content/uploads/2025/02/¡Un-Entrenamiento-768x439.png") == (
        "https://inspiringnews.ai/wp-content/uploads/2025/02/%C2%A1Un-Entrenamiento-768x439.png"
    )
    already = "https://inspiringnews.ai/wp-content/uploads/2026/09/9_2024_%C2%A9Isabelle.jpg"
    assert images.address(already) == already
