"""
Nothing a fact-checker could not have read when the claim was made.

A benchmark claim was checked by somebody, and that fact-check is on the web
now. Searching today for a claim from October 2020 returns the verdict itself:
on 2026-11-05, for the AVeriTeC claim about Sean Connery's letter to Steve
Jobs, the first results were Snopes, Reuters and PolitiFact. Reading that is
not verifying, and it inflates exactly the number being measured.

ClaimCheck (Putta et al., 2025) restricts its search to before the claim's
date, by Google's own date filter through a paid API. Nothing free does that
from here (tried 2026-11-05): SearXNG has no absolute date range and its engines
ignored a `before:` operator (as many results after the date as without it),
Google does not answer through SearXNG, and asked directly DuckDuckGo and
Mojeek challenged the request and Brave answered 429. So the search stays open
and **this gate decides**: a page is evidence only if it can be shown to predate
the claim.

- `ArticleContext.evidence_before` is the claim's date. None, the app's case,
  and nothing here runs.
- A page is late when any date known for it, the search engine's, the page's
  or the one in its address, is on or after the cutoff: "before the claim's
  annotated publication date", so the day itself counts as late.
- A page with no date is dropped by default (`evidence_undated: drop`): what
  cannot be shown to predate the claim cannot be used.
- A page that is rewritten for as long as it exists is refused whatever its date
  says (`LIVING_SITES`). Found in the first check, 2026-11-05: Wikipedia's
  "Walmart" passed as dated 2001-09-12, the day it was created, holding today's
  text. An archived copy of one is fine: its address says when it was taken.

- A page with no date that is a fact-check, by its site, address or title, or
  that is on the site of the claim's own fact-check, is refused whatever
  `evidence_undated` says (`FACT_CHECK`). Found on the first knowledge-store
  claims, 2026-11-05: the claim's fact-check was at fit.thequint.com and the
  store held it at www.thequint.com/fit/..., so no comparison of addresses saw
  it, and the model answered from it. A fact-check dated before the claim is
  fair: it was there to be read.
- A page whose own text states a date on or after the cutoff is refused, whatever
  else it says of itself (`LATE_IN_TEXT`). Found in the first 100 knowledge-store
  claims, 2026-11-05, after their audit had said all was well: 33 of the 480
  sources did, most with no date anywhere else, among them AP's and ABC's reports
  of the very day of the claim, and Mayo Clinic's page "updated" in 2022. A page
  written in time can name a date still to come (an election's), and is lost with
  the rest: that costs a replacement from further down the ranking, the other
  mistake costs the measurement. A snapshot older than the cutoff is exempt: its
  address proves when its text existed, so a later date in it can only be a plan.

What it cannot see, and a report must say: a page edited since with no date in
its text, or one published in time and rewritten without a trace. Only a snapshot
from the time could rule that out.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from urllib.parse import urlsplit

from src.models.fact_checker.evidence import Evidence, RejectedEvidence
from src.models.fact_checker.pipeline_stage import PipelineStage

BEFORE = "before"
LATE = "late"
UNDATED = "undated"
LIVING = "living"
FACT_CHECK = "fact-check"
LATE_IN_TEXT = "late-in-text"

# Why a page was refused, as the run's record says it. `rejected` is the only
# trace of what the gate did, so the report counts by these exact strings.
REASON_LATE = "published on or after the claim's date (temporal cutoff)"
REASON_UNDATED = "no date to show it predates the claim (temporal cutoff)"
REASON_LATE_IN_TEXT = "its text states a date on or after the claim's (temporal cutoff)"

REASON_LIVING = "rewritten continually: its date is not its text's (temporal cutoff)"

# Reference works, whose date is at best when the page began. One test for what
# belongs here: does the text served today state what happened after the date
# it carries? News archives, papers and official releases mostly do not.
LIVING_SITES = (
    "wikipedia.org",
    "wikimedia.org",
    "wikidata.org",
    "wiktionary.org",
    "wikiquote.org",
    "fandom.com",
    "britannica.com",
    "ballotpedia.org",
    "everybodywiki.com",
)

REASON_FACT_CHECK = "a fact-check with no date to show it predates the claim (temporal cutoff)"

# Sites that do nothing else. From AVeriTeC's own sources (the fact-checking
# articles of its train and dev splits), plus the two largest it does not use.
# General outlets with a fact-check desk are not here: their other pages are
# news, and the address or title below catches the desk's.
FACT_CHECK_SITES = (
    "politifact.com", "snopes.com", "truthorfiction.com", "africacheck.org", "leadstories.com",
    "fullfact.org", "factcheck.org", "checkyourfact.com", "boomlive.in", "dubawa.org",
    "altnews.in", "polygraph.info", "factly.in", "misbar.com", "vishvasnews.com",
    "verafiles.org", "healthfeedback.org", "climatefeedback.org", "sciencefeedback.co",
    "ghanafact.com", "factcheckni.org", "covid19facts.ca", "namibiafactcheck.org.na",
    "zimfact.org", "pesacheck.org", "theferret.scot",
)

_FACT_CHECK_WORDS = re.compile(
    r"fact[\s_-]*check|webqoof|debunk|\bhoax|fake[\s_-]*news|false[\s_-]*claim|misleading[\s_-]*claim",
    re.IGNORECASE,
)

# A second-level name that is not the outlet: example.co.uk is three labels.
_SECOND_LEVEL = {"co", "com", "org", "net", "gov", "ac", "edu"}

# How many pages one claim may fetch looking for dated ones. An undated
# candidate only shows its date once fetched, so the top five can all be
# refused; going down the ranking replaces them, at a cost bounded here.
FETCH_FACTOR = 3

_MONTHS = {
    name: number
    for number, name in enumerate(
        ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"),
        start=1,
    )
}

_MONTH = r"0?[1-9]|1[0-2]|jan[a-z]*|feb[a-z]*|mar[a-z]*|apr[a-z]*|may|jun[a-z]*|jul[a-z]*|aug[a-z]*|sep[a-z]*|oct[a-z]*|nov[a-z]*|dec[a-z]*"

# /2020/11/03/, /2020/nov/03/, /2020-11-03-, /2020/11/
_PATH_DATE = re.compile(
    rf"/((?:19|20)\d{{2}})[/-]({_MONTH})(?:[/-](0?[1-9]|[12]\d|3[01]))?(?=[/\-_.]|$)",
    re.IGNORECASE,
)

# /20201103 or -20201103-, eight digits with a real month and day in them.
_COMPACT_DATE = re.compile(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)")

_ARCHIVED = re.compile(r"^https?://web\.archive\.org/web/(\d{4})(\d{2})(\d{2})\d*[a-z_]*/(.+)$", re.IGNORECASE)

_MONTH_WORD = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"

# October 2, 2020 and Oct. 2nd 2020
_TEXT_MONTH_DAY = re.compile(
    rf"\b{_MONTH_WORD}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)

# 2 October 2020
_TEXT_DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MONTH_WORD},?\s+((?:19|20)\d{{2}})\b",
    re.IGNORECASE,
)

# 2020-10-02
_TEXT_ISO = re.compile(r"(?<!\d)((?:19|20)\d{2})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?!\d)")

# October 2020
_TEXT_MONTH_YEAR = re.compile(rf"\b{_MONTH_WORD},?\s+((?:19|20)\d{{2}})\b", re.IGNORECASE)


def unarchived(url: str) -> str:
    """The address an archive.org snapshot is a copy of; any other unchanged."""

    match = _ARCHIVED.match((url or "").strip())

    return match.group(4) if match else (url or "")


def date_in_url(url: str) -> date | None:
    """
    The publication date a news address states, or None. Month-only addresses
    (/2020/11/) read as the month's last day: the page may be from any day of
    it, and this is used to refuse pages, so it assumes the latest.

    A snapshot's address says when archive.org saw the page, which proves it
    existed then, so that date stands over any in the original address.
    """

    archived = _ARCHIVED.match((url or "").strip())

    if archived:
        return _real_date(archived.group(1), archived.group(2), archived.group(3))

    path = re.sub(r"^[a-z]+://[^/]+", "", (url or "").strip(), flags=re.IGNORECASE).split("?")[0]

    match = _PATH_DATE.search(path)

    if match:
        return _real_date(match.group(1), match.group(2), match.group(3))

    match = _COMPACT_DATE.search(path)

    if match:
        return _real_date(match.group(1), match.group(2), match.group(3))

    return None


def _real_date(year: str, month: str, day: str | None) -> date | None:

    number = int(month) if month.isdigit() else _MONTHS.get(month[:3].lower())

    if number is None:
        return None

    last = calendar.monthrange(int(year), number)[1]

    try:
        found = date(int(year), number, int(day) if day else last)
    except ValueError:
        return None

    # A date still to come is digits, not a date: "20300225" in ScienceDirect's
    # S0010440X20300225 refused a good paper as published in 2030.
    return found if found <= date.today() else None


def known_dates(item: Evidence) -> list[date]:
    """Every date known for a page: the search's or the page's, and its address's."""

    dates = [item.published_at.date()] if item.published_at else []

    in_url = date_in_url(item.url)

    if in_url:
        dates.append(in_url)

    return dates


def dates_in_text(text: str | None) -> list[date]:
    """
    Every date a text states with at least a month and a year. A bare month reads
    as its first day, unlike an address's: text names months for all sorts of
    reasons, and "October 2020" says nothing against a claim of 13 October.
    """

    text = text or ""

    found: list[date | None] = []

    found += [_real_date(m.group(3), m.group(1), m.group(2)) for m in _TEXT_MONTH_DAY.finditer(text)]
    found += [_real_date(m.group(3), m.group(2), m.group(1)) for m in _TEXT_DAY_MONTH.finditer(text)]
    found += [_real_date(m.group(1), m.group(2), m.group(3)) for m in _TEXT_ISO.finditer(text)]
    found += [_real_date(m.group(2), m.group(1), "1") for m in _TEXT_MONTH_YEAR.finditer(text)]

    return [day for day in found if day]


def latest_in_text(item: Evidence) -> date | None:
    """The latest date a page's title, snippet or text states, or None."""

    days = [
        day
        for part in (item.title, item.snippet, item.content)
        for day in dates_in_text(part)
    ]

    return max(days) if days else None


def proved_older(url: str, cutoff: date) -> bool:
    """A snapshot taken before the cutoff: its text existed then, whatever it names."""

    day = date_in_url(url) if _ARCHIVED.match((url or "").strip()) else None

    return day is not None and day < cutoff


def is_living(url: str) -> bool:
    """A reference work's page as served today; never an archived copy of one."""

    if _ARCHIVED.match((url or "").strip()):
        return False

    host = urlsplit((url or "").strip()).netloc.lower().split(":")[0]

    return any(host == site or host.endswith("." + site) for site in LIVING_SITES)


def _host(url: str) -> str:

    return urlsplit(unarchived(url or "").strip()).netloc.lower().split(":")[0].removeprefix("www.")


def site_of(url: str) -> str:
    """fit.thequint.com -> thequint.com; news.bbc.co.uk -> bbc.co.uk."""

    labels = _host(url).split(".")

    if len(labels) < 2:
        return ".".join(labels)

    keep = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2 else 2

    return ".".join(labels[-keep:])


def looks_like_fact_check(url: str, title: str | None = None) -> bool:
    """A fact-check by its site (including a factcheck.* desk), its address or its title."""

    host = _host(url)

    if _FACT_CHECK_WORDS.search(host) or any(host == site or host.endswith("." + site) for site in FACT_CHECK_SITES):
        return True

    path = urlsplit(unarchived(url or "").strip()).path

    return bool(_FACT_CHECK_WORDS.search(path) or _FACT_CHECK_WORDS.search(title or ""))


def standing(item: Evidence, cutoff: date, fact_check: str | None = None) -> str:
    """
    BEFORE, LATE, LATE_IN_TEXT, LIVING, FACT_CHECK or UNDATED. One late date is
    enough, a reference work's date is not believed, and a page with no date that
    could be the verdict is not given the benefit of the doubt: the gate refuses
    on doubt.

    `fact_check` is the address of the claim's own fact-check, if it has one.
    """

    if is_living(item.url):
        return LIVING

    dates = known_dates(item)

    if any(day >= cutoff for day in dates):
        return LATE

    if not proved_older(item.url, cutoff):

        latest = latest_in_text(item)

        if latest and latest >= cutoff:
            return LATE_IN_TEXT

    if not dates:

        if looks_like_fact_check(item.url, item.title):
            return FACT_CHECK

        if fact_check and site_of(item.url) == site_of(fact_check):
            return FACT_CHECK

        return UNDATED

    return BEFORE


# What is refused whatever `evidence_undated` says.
_REASONS = {
    LATE: REASON_LATE,
    LATE_IN_TEXT: REASON_LATE_IN_TEXT,
    LIVING: REASON_LIVING,
    FACT_CHECK: REASON_FACT_CHECK,
}


def _refused(item: Evidence, reason: str) -> RejectedEvidence:

    return RejectedEvidence(
        url=item.url,
        title=item.title,
        origin=item.origin,
        stage=PipelineStage.EVIDENCE_RETRIEVAL,
        reason=reason,
        score=item.relevance_score,
    )


def without_late(
    evidence: list[Evidence],
    cutoff: date | None,
    fact_check: str | None = None,
) -> tuple[list[Evidence], list[RejectedEvidence]]:
    """
    Candidates with a date on or after the cutoff refused, before any is
    fetched: most of them say so in their address. Undated ones go on, since
    fetching a page is how its date is found.
    """

    if cutoff is None:
        return evidence, []

    kept, refused = [], []

    for item in evidence:

        reason = _REASONS.get(standing(item, cutoff, fact_check))

        if reason:
            refused.append(_refused(item, reason))
        else:
            kept.append(item)

    return kept, refused


def within(
    evidence: list[Evidence],
    cutoff: date | None,
    undated: str = "drop",
    fact_check: str | None = None,
) -> tuple[list[Evidence], list[RejectedEvidence]]:
    """The final say, once a page's own date is known. Input order kept."""

    if cutoff is None:
        return evidence, []

    kept, refused = [], []

    for item in evidence:

        where = standing(item, cutoff, fact_check)

        reason = _REASONS.get(where)

        if reason:
            refused.append(_refused(item, reason))
        elif where == UNDATED and undated != "keep":
            refused.append(_refused(item, REASON_UNDATED))
        else:
            kept.append(item)

    return kept, refused
