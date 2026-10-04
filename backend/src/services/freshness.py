"""
How long an article takes to reach us after it is published, per source.

For every article in the lake, four moments, each from where it is
actually recorded:

    published   the feed item's time (sightings, from discovery), else the
                page's own article:published_time / datePublished (the raw
                record's article.metadata.publishedTime), else only the
                date the page states (article.published_at)
    first seen  when ingestion first discovered the URL (sightings); none
                for an article someone posted by hand
    fetched     the earliest raw record's fetched_at
    available   the earliest exploitation record marked publishable - when
                the reader view could first show it

and the lags between them, in hours:

    seen        published -> first seen   the source's feed and our polling
    queue       first seen -> fetched     our own backlog
    reception   published -> fetched      the whole delay until we had it
    available   published -> available    until a reader could see it

A lag is computed only between two precise times. An article whose page
states only a date gets `receptionDays` instead (fetched date minus
published date, ±1 day), counted apart: setting a date to midnight would
invent hours of delay. A negative lag - published after we fetched it, a
wrong timezone or a feed that rewrites its times - is counted and kept
out of the medians rather than averaged in.

What the numbers mean today: ingestion runs only when someone presses
Ingest, so "seen" is mostly the time until the next press. The split is
what makes that visible: "queue" and "available" are the pipeline's own,
and they do not depend on how often anyone presses.

Read from the lake on demand, like article_stats: the lake is the record.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone

from src.evaluation.stats import median, percentile, rounded
from src.models.storage.lineage import DataLayer
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of

# How many articles the response lists, newest fetch first. The
# aggregates cover all of them.
ARTICLES_LISTED = 200

FEED, PAGE, DATE = "feed", "page", "date"


def _time(value) -> datetime | None:
    """
    An aware UTC datetime. The lake writes naive local times
    (datetime.now), so a naive value is read as this machine's local
    time - the clock that wrote it.
    """

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.astimezone()

    return parsed.astimezone(timezone.utc)


def _naive(value) -> bool:
    """
    The page stated a time but no timezone. It is read as this machine's
    local time like any naive value, which may be hours off the
    publisher's; such articles are counted (`noTimezone`).
    """

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).tzinfo is None
    except ValueError:
        return False


def _day(value) -> date | None:

    if value is None or value == "":
        return None

    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _hours(start: datetime | None, end: datetime | None) -> float | None:

    if start is None or end is None:
        return None

    return (end - start).total_seconds() / 3600


def _iso(value: datetime | None) -> str | None:

    return value.isoformat(timespec="seconds") if value else None


def _source_url(record: dict) -> str:

    return str((record.get("lineage") or {}).get("source_url") or record.get("url") or "")


def _produced(record: dict) -> datetime | None:

    return _time((record.get("lineage") or {}).get("produced_at"))


def _earliest(current: datetime | None, candidate: datetime | None) -> datetime | None:

    if candidate is None:
        return current

    return candidate if current is None or candidate < current else current


def freshness(lake, sightings: dict[str, dict] | None = None) -> dict:
    """
    `lake` is anything with DataLakeRepository's `list(layer)`;
    `sightings` is Sightings.all() - comparable_url -> first sighting.
    """

    sightings = sightings or {}

    articles: dict[str, dict] = {}

    for record in lake.list(DataLayer.RAW):

        url = _source_url(record)

        if not url:
            continue

        key = comparable_url(url)
        article = record.get("article") or {}
        fetched = _time(record.get("fetched_at")) or _produced(record)

        entry = articles.setdefault(key, {
            "url": url,
            "sourceId": article.get("source_id"),
            "domain": domain_of(url),
            "title": article.get("title"),
            "fetched": None,
            "pageTime": None,
            "pageNaive": False,
            "date": None,
            "analysed": None,
            "available": None,
            "publishable": False,
        })

        # The first fetch is when we received it; a re-analysis later
        # is not a second reception.
        if fetched is not None and (entry["fetched"] is None or fetched < entry["fetched"]):
            entry["fetched"] = fetched
            entry["title"] = article.get("title") or entry["title"]

        page_time = (article.get("metadata") or {}).get("publishedTime")

        if page_time and entry["pageTime"] is None:
            entry["pageTime"] = _time(page_time)
            entry["pageNaive"] = _naive(page_time)

        entry["date"] = entry["date"] or _day(article.get("published_at"))

    for record in lake.list(DataLayer.PROCESSED):

        entry = articles.get(comparable_url(_source_url(record)))

        if entry is not None:
            entry["analysed"] = _earliest(entry["analysed"], _produced(record))

    for record in lake.list(DataLayer.EXPLOITATION):

        entry = articles.get(comparable_url(_source_url(record)))

        if entry is not None and record.get("publishable"):
            entry["publishable"] = True
            entry["available"] = _earliest(entry["available"], _produced(record))

    rows = [_row(key, entry, sightings.get(key)) for key, entry in articles.items()]

    rows.sort(key=lambda row: row["fetchedAt"] or "", reverse=True)

    by_source: dict[str, list[dict]] = defaultdict(list)

    for row in rows:
        by_source[row["sourceId"] or row["domain"]].append(row)

    sources = [{"source": source, **_summary(group)} for source, group in by_source.items()]
    sources.sort(key=lambda entry: entry["articles"], reverse=True)

    return {
        "totals": _summary(rows),
        "sources": sources,
        "articles": rows[:ARTICLES_LISTED],
        "sightings": len(sightings),
    }


def _row(key: str, entry: dict, sighting: dict | None) -> dict:

    feed_time = _time((sighting or {}).get("feedPublishedAt"))
    first_seen = _time((sighting or {}).get("firstSeenAt"))

    if feed_time is not None:
        published, precision = feed_time, FEED
    elif entry["pageTime"] is not None:
        published, precision = entry["pageTime"], PAGE
    else:
        published, precision = None, DATE if entry["date"] else None

    fetched = entry["fetched"]

    lags = {
        "seen": _hours(published, first_seen),
        "queue": _hours(first_seen, fetched),
        "reception": _hours(published, fetched),
        "processing": _hours(fetched, entry["analysed"]),
        "available": _hours(published, entry["available"]),
    }

    reception_days = None

    if precision == DATE and fetched is not None:
        reception_days = (fetched.date() - entry["date"]).days

    return {
        "key": key,
        "url": entry["url"],
        "sourceId": entry["sourceId"],
        "domain": entry["domain"],
        "title": entry["title"],
        "via": "ingestion" if sighting else "posted",
        "publishedAt": _iso(published) if published else (entry["date"].isoformat() if entry["date"] else None),
        "publishedFrom": precision,
        "noTimezone": precision == PAGE and entry["pageNaive"],
        "firstSeenAt": _iso(first_seen),
        "fetchedAt": _iso(fetched),
        "analysedAt": _iso(entry["analysed"]),
        "availableAt": _iso(entry["available"]),
        "publishable": entry["publishable"],
        "lagHours": {name: rounded(value, 2) for name, value in lags.items()},
        "receptionDays": reception_days,
    }


def _stat(values: list[float]) -> dict:
    """Median and p90 of the non-negative values; negatives counted apart."""

    kept = [value for value in values if value >= 0]

    return {
        "n": len(kept),
        "median": rounded(median(kept), 2),
        "p90": rounded(percentile(kept, 90), 2),
        "negative": len(values) - len(kept),
    }


def _summary(rows: list[dict]) -> dict:

    def lags(name: str) -> list[float]:
        return [row["lagHours"][name] for row in rows if row["lagHours"][name] is not None]

    days = [row["receptionDays"] for row in rows if row["receptionDays"] is not None]

    return {
        "articles": len(rows),
        "ingested": sum(1 for row in rows if row["via"] == "ingestion"),
        "publishable": sum(1 for row in rows if row["publishable"]),
        "publishedFrom": {
            FEED: sum(1 for row in rows if row["publishedFrom"] == FEED),
            PAGE: sum(1 for row in rows if row["publishedFrom"] == PAGE),
            DATE: sum(1 for row in rows if row["publishedFrom"] == DATE),
            "none": sum(1 for row in rows if row["publishedFrom"] is None),
        },
        "noTimezone": sum(1 for row in rows if row["noTimezone"]),
        "hours": {name: _stat(lags(name)) for name in ("seen", "queue", "reception", "processing", "available")},
        "receptionDays": _stat([float(value) for value in days]),
    }
