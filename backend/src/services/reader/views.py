"""
What a reader is shown of one analysed article, built from what the lake
already holds. Nothing here re-runs a stage.

Two shapes:

- a feed card (`card`): the exploitation record, plus a per-claim tally
  read once from the processed record - "1 true, 2 unverified" says far
  more than the article's worst-claim-wins verdict alone, which lets one
  UNVERIFIED outweigh any number of TRUE;
- the article view (`article_view`): the card plus every checked claim,
  the sources it rests on, and why each source was trusted.

Reads plain dicts rather than validating into the pydantic models. The
lake holds records written by every past version of the pipeline - the
oldest predate pertinence, `reliability_known` and the unreachable flags -
and a reader that refuses an old record shows nothing for it. A missing
field leaves a gap, as in the frontend's liveTrace.ts.

Never includes a scraped body. Evidence `content` is a third party's whole
page, and the article's own body is somebody else's journalism: the
reader shows the lead the lake already keeps (`summary`) and links to the
original.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Iterable
from urllib.parse import unquote, urlsplit

from src.models.core.source import NewsSource
from src.models.fact_checker.fact_check import Verdict
from src.services.fact_checker.progress import QUOTE_CHARS, SNIPPET_CHARS
from src.services.fact_checker.verification.llm_verification import (
    INVALID_OUTPUT_EXPLANATION,
)
from src.services.scraper.article_stats import comparable_url
from src.services.scraper.request_stats import domain_of

# A feed card's excerpt. The article view gets the whole stored lead
# (the exploitation layer keeps the body's first 500 characters).
CARD_EXCERPT_CHARS = 240

# Per claim. A claim can touch a few dozen candidates; past this the list
# is noise to a reader, and the count still says how many there were.
MAX_NOT_USED = 20

# Statements in the article that were never checked: listed, not judged.
MAX_UNCHECKED = 20

# How a claim's check ended. Derived here, once, so the frontend phrases
# it rather than re-deriving it from four fields.
JUDGED = "judged"
# The model gave a definite answer but could not point to a source that
# bears it out, so the guardrail in ConfidenceScorer turned it into
# UNVERIFIED. The model's answer is kept (`modelVerdict`), not hidden.
UNGROUNDED = "ungrounded"
# The search ran and nothing that addresses the claim came back. A real
# UNVERIFIED: the claim was looked for and not found.
NO_EVIDENCE = "no_evidence"
# The three below are failures of ours, not findings about the claim. An
# UNVERIFIED on any of them says nothing either way, so they are counted
# apart from the verdicts and never shown as one.
SEARCH_UNAVAILABLE = "search_unavailable"
LLM_UNREACHABLE = "llm_unreachable"
NO_ANSWER = "no_answer"

NOT_JUDGED = (SEARCH_UNAVAILABLE, LLM_UNREACHABLE, NO_ANSWER)

# Shown when no claim of an article was actually judged - in place of the
# overall verdict, which would otherwise read "UNVERIFIED" as if someone
# had looked and found nothing.
NOT_CHECKED = "NOT_CHECKED"

_DEFINITIVE = {
    Verdict.TRUE.value,
    Verdict.PARTIALLY_TRUE.value,
    Verdict.FALSE.value,
    Verdict.MISLEADING.value,
}

_VERDICT_ORDER = [verdict.value for verdict in Verdict]


# ----------------------------------------------------------------------
# Identity
# ----------------------------------------------------------------------


def reader_id(url: str) -> str:
    """
    The id an article has in the reader: its host and path, hashed.

    Not the lake's `article_id`, which is minted per extraction - every
    re-analysis of the same article gets a new one, and a link to the
    article would break each time. Host and path are the same comparison
    ingestion uses to decide an article is already stored, so a tracking
    parameter or a trailing slash is the same article here too.
    """

    return hashlib.sha256(comparable_url(url).encode("utf-8")).hexdigest()[:16]


class SourceNames:
    """
    "BBC News" rather than "bbc" or "web". Articles that came through
    ingestion carry their source YAML's id; articles someone posted by
    URL carry "web", and are named by matching their domain against the
    configured sources' base URLs. Anything else is shown as its domain.
    """

    def __init__(self, sources: Iterable[NewsSource] = ()):

        self.by_id: dict[str, str] = {}
        self.by_domain: dict[str, str] = {}

        for source in sources:
            self.by_id[source.id] = source.name
            self.by_domain[domain_of(str(source.base_url))] = source.name

    def describe(self, source_id: str | None, url: str) -> dict:

        domain = domain_of(url)

        name = self.by_id.get(source_id or "") or self._by_domain(domain) or domain

        return {"id": source_id, "name": name, "domain": domain}

    def _by_domain(self, domain: str) -> str | None:

        # news.bbc.co.uk -> bbc.co.uk -> co.uk: a section subdomain is
        # still the same outlet. Stops before a bare suffix.
        labels = domain.split(".")

        for start in range(len(labels) - 1):

            name = self.by_domain.get(".".join(labels[start:]))

            if name:
                return name

        return None


# ----------------------------------------------------------------------
# Text
# ----------------------------------------------------------------------


_SPACE = re.compile(r"\s+")

_SLUG_WORDS = re.compile(r"[-_+]+")


def excerpt(text: str | None, limit: int) -> str:
    """
    At most `limit` characters, cut at a word boundary and marked with an
    ellipsis when anything was cut. The stored lead is itself a hard cut
    at 500 characters, usually mid-word, so it gets the same treatment.
    """

    text = _SPACE.sub(" ", text or "").strip()

    # `<`, not `<=`: a lead exactly 500 long is one the writer cut there
    # (DataLakeRepository stores body[:500]), so it is treated as cut.
    if len(text) < limit:
        return text

    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.-")

    return f"{cut}…"


def headline(title: str | None, url: str, lead: str | None = None) -> str:
    """
    The article's title, or - when extraction found none, which the lake
    shows is common for pages posted by hand - a stand-in: the URL slug,
    which on most news sites is the headline in lowercase; else the lead's
    first sentence; else the domain. Callers flag the fallback
    (`titleExtracted`), so a stand-in is never passed off as the title.
    """

    title = _SPACE.sub(" ", title or "").strip()

    if title:
        return title

    path = unquote(urlsplit(url.strip()).path)

    # A slug is several words joined by hyphens: "/2026/09/18/some-story/"
    # and "/ciencia/some-story/" both name the story in one segment. An
    # opaque id ("/articles/c0k4x2y3z") is one "word" and is skipped, or
    # it would be shown as the headline.
    slugs = [
        words
        for words in (
            _SLUG_WORDS.sub(" ", re.sub(r"\.[a-z0-9]{2,5}$", "", segment)).strip()
            for segment in path.split("/")
        )
        if len(words.split()) >= 3 and re.search(r"[^\W\d_]", words)
    ]

    if slugs:
        words = max(slugs, key=len)
        return words[0].upper() + words[1:]

    sentence = re.split(r"(?<=[.!?])\s", _SPACE.sub(" ", lead or "").strip(), maxsplit=1)[0]

    if sentence:
        return excerpt(sentence, 110)

    return domain_of(url)


# ----------------------------------------------------------------------
# Claims
# ----------------------------------------------------------------------


def claim_outcome(check: dict) -> str:
    """
    How a claim's check ended, in the order the causes take precedence -
    the same order FactChecker._trace reports them in.
    """

    if check.get("llm_unreachable"):
        return LLM_UNREACHABLE

    if not check.get("evidence"):
        return SEARCH_UNAVAILABLE if check.get("search_unavailable") else NO_EVIDENCE

    if check.get("explanation") == INVALID_OUTPUT_EXPLANATION:
        return NO_ANSWER

    raw_verdict = check.get("raw_verdict")

    if check.get("verdict") == Verdict.UNVERIFIED.value and raw_verdict in _DEFINITIVE:
        return UNGROUNDED

    return JUDGED


def _checks(processed: dict | None) -> list[dict]:

    fact_check = (processed or {}).get("fact_check") or {}

    return [check for check in fact_check.get("claim_checks") or [] if isinstance(check, dict)]


def verdict_summary(exploitation: dict, processed: dict | None) -> dict:
    """
    The article's verdict as a reader should weigh it: the overall verdict
    the pipeline decided, next to how each checked claim came out.

    `counts` holds only claims that were actually judged. A claim whose
    search failed or whose model never answered is UNVERIFIED in the
    record, but counting it as one would present our outage as a finding
    about the article; those go to `notJudged` instead.
    """

    checks = _checks(processed)

    outcomes = [claim_outcome(check) for check in checks]

    judged = [
        check.get("verdict")
        for check, outcome in zip(checks, outcomes)
        if outcome not in NOT_JUDGED
    ]

    tally = Counter(judged)

    overall = exploitation.get("verdict") or Verdict.UNVERIFIED.value

    fact_check = (processed or {}).get("fact_check") or {}

    return {
        "overall": overall,
        # What to show as the headline verdict: NOT_CHECKED when no claim
        # was judged at all. Without the processed record there is no
        # tally to tell, and the overall verdict is all that is known.
        "display": overall if judged or processed is None else NOT_CHECKED,
        "confidence": exploitation.get("verdict_confidence"),
        "claimsTotal": exploitation.get("claims_total") or 0,
        "claimsChecked": len(checks) if processed else exploitation.get("claims_checked") or 0,
        "counts": {verdict: tally[verdict] for verdict in _VERDICT_ORDER if tally[verdict]},
        "notJudged": sum(outcome in NOT_JUDGED for outcome in outcomes),
        "searchUnavailable": outcomes.count(SEARCH_UNAVAILABLE),
        "llmUnreachable": outcomes.count(LLM_UNREACHABLE),
        "noAnswer": outcomes.count(NO_ANSWER),
        "sourcesCited": len(exploitation.get("cited_evidence_urls") or []),
        # Fewer anchor claims than the article's credibility is meant to
        # be judged by: the verdict stands for what was checked, but it
        # rests on less than usual.
        "belowAnchorFloor": bool(fact_check.get("below_anchor_floor")),
    }


def source_view(item: dict, cited: bool) -> dict:
    """
    One source behind a claim, and why it was trusted: whether the model
    relied on it, what it says about the claim, the span it was judged on,
    how well it addresses the claim, and the reliability rating - with
    `reliabilityKnown` saying whether that rating is ours or the default
    every unrated domain gets.
    """

    url = str(item.get("url") or "")

    quote = item.get("quote")

    return {
        "url": url,
        "title": item.get("title") or "",
        "domain": item.get("domain") or domain_of(url),
        "origin": item.get("origin") or "web",
        "publishedAt": item.get("published_at"),
        "snippet": (item.get("snippet") or "")[:SNIPPET_CHARS],
        "cited": cited,
        "stance": item.get("stance"),
        "quote": quote[:QUOTE_CHARS] if quote else None,
        "reliabilityKnown": bool(item.get("reliability_known")),
        # Which of the claim's searches found it: the one for who and
        # what, the one for what the claim asserts, or the one looking
        # for counter-evidence.
        "foundBy": item.get("found_by") or [],
        "scores": {
            "relevance": item.get("relevance_score"),
            "pertinence": item.get("pertinence_score"),
            "semantic": item.get("semantic_score"),
            "lexical": item.get("lexical_score"),
            "recency": item.get("recency_score"),
            "reliability": item.get("reliability_score"),
        },
    }


def claim_view(index: int, check: dict) -> dict:

    evidence = [item for item in check.get("evidence") or [] if isinstance(item, dict)]

    cited = set(check.get("cited_evidence_indices") or [])

    # Indices are resolved before anything is reordered: they are what
    # the model cited by number, and re-pointing one would attribute a
    # citation to the wrong page.
    sources = [source_view(item, index in cited) for index, item in enumerate(evidence)]

    # Cited first; otherwise the ranker's order, which the stable sort keeps.
    sources.sort(key=lambda source: not source["cited"])

    listed = {source["url"] for source in sources}

    # A ranked source the model did not cite is both in the evidence and
    # among the rejected ("not cited by the LLM"). It is already shown,
    # with its scores, as a source; listing it twice would count it twice.
    not_used = [
        {
            "url": str(item.get("url") or ""),
            "title": item.get("title") or "",
            "stage": item.get("stage"),
            "reason": item.get("reason") or "",
        }
        for item in check.get("rejected_sources") or []
        if isinstance(item, dict) and item.get("url") not in listed
    ]

    raw_verdict = check.get("raw_verdict")

    verdict = check.get("verdict") or Verdict.UNVERIFIED.value

    return {
        "index": index,
        "text": check.get("claim") or "",
        "verdict": verdict,
        "confidence": check.get("confidence"),
        "outcome": claim_outcome(check),
        "explanation": check.get("explanation") or "",
        # What the model itself said, when the guardrails changed it.
        "modelVerdict": raw_verdict if raw_verdict and raw_verdict != verdict else None,
        "note": check.get("stage_note"),
        # Set even when other evidence exists: the verdict then rests on
        # previously analysed articles only, never on the web.
        "searchUnavailable": bool(check.get("search_unavailable")),
        "independentDomains": check.get("independent_domains") or 0,
        "agreements": check.get("agreements") or [],
        "discrepancies": check.get("discrepancies") or [],
        "sources": sources,
        "notUsed": not_used[:MAX_NOT_USED],
        "notUsedTotal": len(not_used),
    }


# ----------------------------------------------------------------------
# The two shapes
# ----------------------------------------------------------------------


def card(exploitation: dict, processed: dict | None, names: SourceNames) -> dict:
    """One article in the feed."""

    lineage = exploitation.get("lineage") or {}

    url = str(exploitation.get("url") or lineage.get("source_url") or "")

    title = exploitation.get("title")

    return {
        "id": reader_id(url),
        "url": url,
        "headline": headline(title, url, exploitation.get("summary")),
        "titleExtracted": bool((title or "").strip()),
        "source": names.describe(exploitation.get("source_id"), url),
        "language": exploitation.get("language"),
        "topic": exploitation.get("primary_topic"),
        "publishedAt": exploitation.get("published_at"),
        "checkedAt": lineage.get("produced_at"),
        "excerpt": excerpt(exploitation.get("summary"), CARD_EXCERPT_CHARS),
        "verdict": verdict_summary(exploitation, processed),
    }


def article_view(
    exploitation: dict,
    processed: dict | None,
    raw: dict | None,
    names: SourceNames,
) -> dict:
    """
    The card, plus everything the article page shows: each checked claim
    with its sources, the statements that were not checked, and what the
    check ran with.
    """

    view = card(exploitation, processed, names)

    lineage = exploitation.get("lineage") or {}

    fact_check = (processed or {}).get("fact_check") or {}

    topics = sorted(
        (topic for topic in exploitation.get("topics") or [] if isinstance(topic, dict)),
        key=lambda topic: topic.get("confidence") or 0.0,
        reverse=True,
    )

    unchecked = [
        claim.get("text") or ""
        for claim in fact_check.get("unselected_claims") or []
        if isinstance(claim, dict)
    ]

    view.update({
        "author": ((raw or {}).get("article") or {}).get("author"),
        "summary": excerpt(exploitation.get("summary"), 500),
        "topics": [
            {"topic": topic.get("topic"), "confidence": topic.get("confidence")}
            for topic in topics[:3]
        ],
        "keywords": (exploitation.get("keywords") or [])[:8],
        # False when the processed record - the one holding the claims and
        # their evidence - could not be read. The page then says so,
        # rather than showing an article with no claims as if none had
        # been checked.
        "claimsAvailable": processed is not None,
        "claims": [claim_view(index, check) for index, check in enumerate(_checks(processed))],
        "uncheckedClaims": unchecked[:MAX_UNCHECKED],
        "uncheckedTotal": len(unchecked),
        "checkedWith": {
            "model": (lineage.get("components") or {}).get("llm_model"),
            "pipelineVersion": lineage.get("pipeline_version"),
        },
    })

    return view
