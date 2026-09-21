"""
How a source is described in the phase events a run emits while it is
still running - the live view and the job journal both read these.

Kept apart from the final response (analysis_service._build_evidence) on
purpose: that one is a finished, cached shape; this one is a stream of
partial snapshots, where most fields are still None because the stage that
fills them has not run yet.
"""

from __future__ import annotations

from src.models.fact_checker.evidence import Evidence

# Events are stored in memory, polled every second and journalled, so a
# scraped article body must never ride along in one.
SNIPPET_CHARS = 240
QUOTE_CHARS = 400


def source_summary(item: Evidence, cited: bool | None = None) -> dict:

    summary = {
        "url": item.url,
        "title": item.title,
        "origin": item.origin,
        "domain": item.domain,
        "engines": item.engines,
        "snippet": (item.snippet or "")[:SNIPPET_CHARS],
        "publishedAt": item.published_at.isoformat() if item.published_at else None,
        "relevanceScore": item.relevance_score,
        "semanticScore": item.semantic_score,
        "recencyScore": item.recency_score,
        "reliabilityScore": item.reliability_score,
        "reliabilityKnown": item.reliability_known,
        "stance": item.stance,
        "quote": item.quote[:QUOTE_CHARS] if item.quote else None,
    }

    if cited is not None:
        summary["cited"] = cited

    return summary
