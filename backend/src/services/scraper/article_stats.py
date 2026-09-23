"""
How many articles have actually been scraped and stored, per domain, and
what became of them.

The request counts (request_stats.py) say how often the scraper *asked*;
these say what it has to show for it. An article counts here once it has
a raw record in the lake - fetched, extracted and long enough to use -
which is what every later stage starts from. Evidence pages are fetched
too but never stored, so they appear in the request counts and not here.

Read from the lake on demand rather than counted as articles arrive: the
lake already is the record of what was scraped, and a second counter
beside it would be one more thing that could disagree with it.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from urllib.parse import urlsplit

from src.models.storage.lineage import DataLayer
from src.services.scraper.request_stats import domain_of

# How many days the per-day series covers.
DAILY_WINDOW = 30


def _source_url(record: dict) -> str:

    lineage = record.get("lineage") or {}

    return str(lineage.get("source_url") or record.get("url") or "")


def _produced_on(record: dict) -> str | None:
    """YYYY-MM-DD the record was written, or None if it cannot be read."""

    lineage = record.get("lineage") or {}

    value = lineage.get("produced_at") or record.get("fetched_at")

    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except ValueError:
        return None


def _filled(value) -> bool:

    return value is not None and str(value).strip() != ""


def _comparable_url(url: str) -> str:
    """
    Host and path, so a re-analysis of the same article with a tracking
    parameter or a trailing slash is not counted as a second article.
    """

    return domain_of(url) + urlsplit(url.strip()).path.rstrip("/")


def article_stats(lake) -> dict:
    """
    Per-domain counts over the lake's three layers. `lake` is anything
    with DataLakeRepository's `list(layer)`.
    """

    raw = lake.list(DataLayer.RAW)
    processed = lake.list(DataLayer.PROCESSED)
    exploitation = lake.list(DataLayer.EXPLOITATION)

    domains: dict[str, dict] = defaultdict(lambda: {
        "scraped": 0,
        "urls": set(),
        "contents": set(),
        "withTitle": 0,
        "withAuthor": 0,
        "withDate": 0,
        "totalLength": 0,
        "languages": Counter(),
        "processed": 0,
        "stored": 0,
        "publishable": 0,
        "rejected": 0,
        "first": None,
        "last": None,
    })

    daily: Counter = Counter()

    for record in raw:

        url = _source_url(record)
        entry = domains[domain_of(url)]
        article = record.get("article") or {}
        lineage = record.get("lineage") or {}

        entry["scraped"] += 1
        entry["urls"].add(_comparable_url(url))

        if lineage.get("content_hash"):
            entry["contents"].add(lineage["content_hash"])

        entry["withTitle"] += _filled(article.get("title"))
        entry["withAuthor"] += _filled(article.get("author"))
        entry["withDate"] += _filled(article.get("published_at"))

        entry["totalLength"] += int(
            record.get("content_length") or len(article.get("content") or "")
        )

        entry["languages"][article.get("language") or "unknown"] += 1

        day = _produced_on(record)

        if day:
            daily[day] += 1
            entry["first"] = min(filter(None, [entry["first"], day]))
            entry["last"] = max(filter(None, [entry["last"], day]))

    for record in processed:
        domains[domain_of(_source_url(record))]["processed"] += 1

    for record in exploitation:

        entry = domains[domain_of(_source_url(record))]

        entry["stored"] += 1

        if record.get("publishable"):
            entry["publishable"] += 1
        else:
            entry["rejected"] += 1

    rows = [_row(domain, entry) for domain, entry in domains.items()]
    rows.sort(key=lambda row: row["scraped"], reverse=True)

    return {
        "totals": {
            "domains": sum(1 for row in rows if row["scraped"]),
            "scraped": sum(row["scraped"] for row in rows),
            "uniqueUrls": sum(row["uniqueUrls"] for row in rows),
            "withTitle": sum(row["withTitle"] for row in rows),
            "withAuthor": sum(row["withAuthor"] for row in rows),
            "withDate": sum(row["withDate"] for row in rows),
            "processed": sum(row["processed"] for row in rows),
            "stored": sum(row["stored"] for row in rows),
            "publishable": sum(row["publishable"] for row in rows),
            "rejected": sum(row["rejected"] for row in rows),
        },
        "daily": _daily_series(daily),
        "domains": rows,
    }


def _row(domain: str, entry: dict) -> dict:

    scraped = entry["scraped"]

    return {
        "domain": domain,
        "scraped": scraped,
        "uniqueUrls": len(entry["urls"]),
        "uniqueContents": len(entry["contents"]),
        "withTitle": entry["withTitle"],
        "withAuthor": entry["withAuthor"],
        "withDate": entry["withDate"],
        "avgLength": entry["totalLength"] / scraped if scraped else None,
        "languages": dict(entry["languages"]),
        "processed": entry["processed"],
        "stored": entry["stored"],
        "publishable": entry["publishable"],
        "rejected": entry["rejected"],
        "firstScraped": entry["first"],
        "lastScraped": entry["last"],
    }


def _daily_series(daily: Counter) -> list[dict]:
    """
    The last DAILY_WINDOW days that have any scrape, oldest first. Days
    with none are left out rather than padded - the lake only ever sees
    articles someone posted, so most days are empty and a padded series
    would be almost all zeros.
    """

    days = sorted(daily)[-DAILY_WINDOW:]

    return [{"date": day, "scraped": daily[day]} for day in days]
