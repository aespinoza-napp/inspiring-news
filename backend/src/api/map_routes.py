"""
The news map (docs/goals.md, "News map"): every published article as a
point, its topics in sections, its entities and related articles.

Open, like /reader, and for the same reason: each route returns what the
public reader page already shows anyone - publishable articles, their
title, outlet, day, topics, entities and verdict - and nothing of a body,
a lineage or a scraped page (src/services/news_map/index.py). A key the
frontend attaches for every visitor would protect nothing.

The articles come gzipped with an ETag that changes only when the set of
published articles or the layout does, so a reader's browser revalidates
for a 304 rather than downloading the map again.
"""

from __future__ import annotations

import gzip
import re

from fastapi import APIRouter, Header, HTTPException, Path, Query, Response

from src.container import get_map_index

router = APIRouter(prefix="/map")

DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _send(tag: str, body: bytes, if_none_match: str | None, accept_encoding: str | None) -> Response:
    """The cached gzip as is when the client takes it, else decompressed; 304 when unchanged."""

    headers = {"ETag": tag, "Cache-Control": "no-cache", "Vary": "Accept-Encoding"}

    if if_none_match and tag in [part.strip() for part in if_none_match.split(",")]:
        return Response(status_code=304, headers=headers)

    if "gzip" in (accept_encoding or "").lower():
        return Response(
            content=body,
            media_type="application/json",
            headers={**headers, "Content-Encoding": "gzip"},
        )

    return Response(content=gzip.decompress(body), media_type="application/json", headers=headers)


@router.get("/articles")
def map_articles(
    day: str | None = Query(default=None, pattern=DAY.pattern),
    if_none_match: str | None = Header(default=None),
    accept_encoding: str | None = Header(default=None),
):
    """
    Every published article's place, as columns (one list per field, the
    same index across them), with the map's frame: the five group sectors
    and the 23 topic anchors. `day` (YYYY-MM-DD, Madrid's) keeps one day.
    """

    index = get_map_index()

    tag, body = index.payload("articles", lambda: index.articles_document(day), day or "")

    return _send(tag, body, if_none_match, accept_encoding)


@router.get("/entities")
def map_entities(
    limit: int = Query(default=500, ge=1, le=5000),
    if_none_match: str | None = Header(default=None),
    accept_encoding: str | None = Header(default=None),
):
    """The entities of more than one published article, most mentioned first, each where its articles are."""

    index = get_map_index()

    tag, body = index.payload("entities", lambda: index.entities_document(limit), str(limit))

    return _send(tag, body, if_none_match, accept_encoding)


@router.get("/articles/{article_id}/links")
def map_article_links(
    article_id: str = Path(pattern=r"^[0-9a-f]{16}$"),
    limit: int = Query(default=10, ge=1, le=30),
):
    """
    One article's topics, entities and related articles, each related one
    with what joins them and how much it counts (the weights of
    /graph/related, computed from the lake).
    """

    links = get_map_index().links(article_id, limit)

    if links is None:
        raise HTTPException(status_code=404, detail="No published article with this id.")

    return links
