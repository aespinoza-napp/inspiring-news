"""
Which day an article belongs to: the publication's, Europe/Madrid.

A reader in Madrid opening "today" at 00:30 expects what was published
after midnight there, not after midnight UTC. Timestamps in the lake are
a mix (src/services/reader/index.py::_timestamp): a feed's publication
time is usually zoned; a page's own date often is not, and is then the
outlet's local time. So a naive publication time is read in its source's
zone, from the source YAML's `country` - not as Madrid's: on 29 Oct 11
of the 32 enabled sources were Spanish and 20 wrote in English, from
the UK, the US and Australia. The pipeline's own times (`produced_at`)
are naive server time, read as local like the reader reads them.
"""

from __future__ import annotations

from datetime import date, datetime, tzinfo
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")

UTC = ZoneInfo("UTC")

# A source's `country` to the zone its naive times are in. INT and EU
# (UN News, ESA, The Conversation) publish in UTC or say their zone.
COUNTRY_ZONES: dict[str, tzinfo] = {
    "ES": MADRID,
    "FR": ZoneInfo("Europe/Paris"),
    "GB": ZoneInfo("Europe/London"),
    "UK": ZoneInfo("Europe/London"),
    "US": ZoneInfo("America/New_York"),
    "AU": ZoneInfo("Australia/Sydney"),
    "AR": ZoneInfo("America/Argentina/Buenos_Aires"),
}


def zone_of(country: str | None) -> tzinfo:
    return COUNTRY_ZONES.get((country or "").upper(), UTC)


def _parse(value) -> datetime | None:

    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def publication_day(published_at, checked_at=None, source_zone: tzinfo = MADRID) -> date | None:
    """
    The Madrid day of `published_at`, or of `checked_at` when there is
    none. A naive `published_at` is in `source_zone`; a naive
    `checked_at` is the server's local time.
    """

    published = _parse(published_at)

    if published is not None:

        if published.tzinfo is None:
            published = published.replace(tzinfo=source_zone)

        try:
            return published.astimezone(MADRID).date()
        except (OverflowError, OSError, ValueError):
            return None

    checked = _parse(checked_at)

    if checked is None:
        return None

    try:
        return checked.astimezone(MADRID).date()
    except (OverflowError, OSError, ValueError):
        return None


def today() -> date:
    return datetime.now(MADRID).date()
