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

from fastapi import APIRouter, Header, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field

from src.container import get_map_index, get_map_search
from src.services.news_map.for_you import ReaderProfile, rank
from src.services.news_map.search import MAX_QUERY
from src.services.rate_limit import RateLimited, RateLimiter

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


def client_of(request: Request) -> str:
    """
    Who is searching, for the per-client limit. Every request reaches the
    backend from the frontend's server, so the address is the first in
    X-Forwarded-For: Caddy sets it from the connection (it ignores a
    client's own unless told to trust a proxy) and the map's proxy passes
    it on. Without it, as on localhost, the connection's own address.
    """

    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()

    return first or (request.client.host if request.client else "unknown")


@router.get("/search")
def map_search(
    request: Request,
    q: str = Query(default="", max_length=MAX_QUERY),
    semantic: bool = Query(default=True),
):
    """
    Articles and names for a query, each with why it matched: the name, a
    similar name, in the title, about a topic, or close in meaning.
    `semantic=false` is the type-ahead: names and words only, no
    embedding. `semantic` in the answer says whether meaning was used,
    skipped, or unavailable (inference/ down).
    """

    try:
        return get_map_search().search(q, client_of(request), semantic=semantic)
    except RateLimited as limited:
        raise HTTPException(
            status_code=429,
            detail="Too many searches from here; try again shortly.",
            headers={"Retry-After": str(int(limited.retry_after + 0.999))},
        )


# Per visitor: a ranking is a pass over every published story and one
# product with their vectors - cheap, but a public route all the same.
FOR_YOU_PER_MINUTE = 60

_for_you_limit = RateLimiter(FOR_YOU_PER_MINUTE)


class FollowedItem(BaseModel):
    kind: str = Field(max_length=16)
    key: str = Field(max_length=200)


class ForYouRequest(BaseModel):
    interests: list[FollowedItem] = Field(default_factory=list, max_length=200)
    saved: list[str] = Field(default_factory=list, max_length=1000)
    hidden: list[str] = Field(default_factory=list, max_length=1000)
    factors: dict[str, float] = Field(default_factory=dict, max_length=8)
    limit: int = Field(default=20, ge=1, le=50)


@router.post("/for-you")
def map_for_you(body: ForYouRequest, request: Request):
    """
    The published stories that fit a reader's interests, each with the
    parts of its score and why it is there (src/services/news_map/for_you.py).
    Stores nothing: what the reader follows comes with the request, from
    their account or, signed out, their browser.
    """

    try:
        _for_you_limit.check(client_of(request))
    except RateLimited as limited:
        raise HTTPException(status_code=429, detail="Too many requests from here; try again shortly.",
                            headers={"Retry-After": str(int(limited.retry_after + 0.999))})

    profile = ReaderProfile.of(
        [item.model_dump() for item in body.interests], body.saved, body.hidden, body.factors,
    )

    return rank(get_map_index().search_context(), profile, body.limit)
