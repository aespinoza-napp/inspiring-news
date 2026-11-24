"""
The photos of compared picks, copied beside their round
(src/services/selection/photos.py). No network: the fetch is faked, and
the download's own rules are checked against a faked requests.get.
"""

import pytest

from src.services.scraper.url_guard import BlockedURL
from src.services.selection import photos
from src.services.selection.photos import NotAPhoto, PhotoKeeper, kind_of, name_for

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64


def test_what_is_kept_is_decided_by_the_bytes():

    assert kind_of(JPEG) == "jpg"
    assert kind_of(PNG) == "png"
    assert kind_of(WEBP) == "webp"
    assert kind_of(b"GIF89a" + b"\x00" * 8) == "gif"
    assert kind_of(b"\x00\x00\x00\x1cftypavif" + b"\x00" * 8) == "avif"

    # An SVG can carry script; a page is not a photo.
    assert kind_of(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>') is None
    assert kind_of(b"<!doctype html><html></html>") is None


def test_each_picks_photo_is_kept_under_its_links_hash_and_failures_say_why(tmp_path):

    answers = {
        "https://cdn.example/a.jpg": JPEG,
        "https://cdn.example/b.png": b"<html>a login page</html>",
    }

    def fetch(url):
        if url not in answers:
            raise ConnectionError("refused")
        return answers[url]

    kept = PhotoKeeper(fetch).keep(tmp_path, [
        {"url": "https://news.example/1", "image": "https://cdn.example/a.jpg"},
        {"url": "https://news.example/2", "image": "https://cdn.example/b.png"},
        {"url": "https://news.example/3", "image": "https://cdn.example/gone.jpg"},
        {"url": "https://news.example/4", "image": None},
    ])

    assert list(kept) == ["https://news.example/1", "https://news.example/2", "https://news.example/3"]

    first = kept["https://news.example/1"]
    assert first["file"] == name_for("https://cdn.example/a.jpg", "jpg")
    assert first["contentType"] == "image/jpeg" and first["bytes"] == len(JPEG)
    assert (tmp_path / first["file"]).read_bytes() == JPEG

    assert "not a JPEG" in kept["https://news.example/2"]["error"]
    assert "refused" in kept["https://news.example/3"]["error"]
    assert not list(tmp_path.glob("*.tmp"))


class Response:

    def __init__(self, status=200, headers=None, body=b"", location=None):
        self.status_code = status
        self.headers = dict(headers or {})
        if location:
            self.headers["location"] = location
        self.is_redirect = location is not None
        self.body = body
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)

    def iter_content(self, size):
        for start in range(0, len(self.body), size):
            yield self.body[start:start + size]

    def close(self):
        self.closed = True


def test_a_redirect_is_checked_by_the_guard_like_the_first_hop(monkeypatch):

    asked = []

    def get(url, **kwargs):
        asked.append(url)
        return Response(location="http://127.0.0.1/secret.jpg")

    def guard(url):
        if "127.0.0.1" in url:
            raise BlockedURL("private address")
        return url

    monkeypatch.setattr(photos.requests, "get", get)
    monkeypatch.setattr(photos, "check_url", guard)

    with pytest.raises(BlockedURL):
        photos.download("https://cdn.example/a.jpg")

    assert asked == ["https://cdn.example/a.jpg"]


def test_a_photo_over_the_size_limit_is_refused_by_its_header_or_its_bytes(monkeypatch):

    monkeypatch.setattr(photos, "check_url", lambda url: url)
    monkeypatch.setattr(photos, "MAX_BYTES", 100)

    monkeypatch.setattr(photos.requests, "get", lambda url, **kw: Response(headers={"content-length": "5000"}))
    with pytest.raises(NotAPhoto):
        photos.download("https://cdn.example/big.jpg")

    monkeypatch.setattr(photos.requests, "get", lambda url, **kw: Response(body=JPEG * 4))
    with pytest.raises(NotAPhoto):
        photos.download("https://cdn.example/big.jpg")

    monkeypatch.setattr(photos.requests, "get", lambda url, **kw: Response(body=JPEG))
    assert photos.download("https://cdn.example/small.jpg") == JPEG
