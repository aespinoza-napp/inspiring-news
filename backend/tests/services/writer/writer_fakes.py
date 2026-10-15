"""
Shared pieces for the writer's tests (not a test module: no `test_`
prefix). The analysed article comes from a real throwaway lake, filled
through DataLakeRepository like the pipeline fills it
(tests/services/reader/reader_lake.py); search, page fetches, Qdrant and
the model are fakes.
"""

from __future__ import annotations

from datetime import datetime

from src.models.core.similarity import SimilarArticle
from src.services.reader.index import ReaderIndex
from src.services.reader.views import reader_id
from src.services.writer.analysed_article import AnalysedArticles
from src.services.writer.article_writer import ArticleWriter
from src.services.writer.draft_writer import DraftWriter
from src.services.writer.related_news import RatedDomains, RelatedNewsFinder

from tests.factories import create_article
from tests.services.fact_checker.fakes import FakeExtractorService, FakeLLMClient, FakeSearxngClient
from tests.services.reader.reader_lake import make_lake, publish

ANALYSED_URL = "https://www.bbc.com/news/valley-trees-planted-by-volunteers"


class FakeVectorRepository:
    """
    Stands in for VectorRepository.search: `hits` are (url, similarity,
    title, body, published_at) tuples, returned best first and without
    `exclude_url`, as Qdrant filters it inside the query.
    """

    def __init__(self, hits=None, error: Exception | None = None):
        self.hits = hits or []
        self.error = error
        self.vectors: list[list[float]] = []

    def search(self, vector, limit=5, exclude_url=None):
        self.vectors.append(vector)
        if self.error:
            raise self.error
        results = []
        for url, similarity, title, body, published_at in self.hits:
            if url == exclude_url:
                continue
            results.append(SimilarArticle(
                article=create_article(
                    url=url,
                    title=title,
                    body=body,
                    published_at=published_at,
                    source_id="web",
                ),
                similarity=similarity,
            ))
        return sorted(results, key=lambda hit: hit.similarity, reverse=True)[:limit]


class ExplodingEmbeddings:
    """The corpus must be searched with the stored embedding, not a new one."""

    def encode(self, text):
        raise AssertionError("encode() called: the stored embedding should have been used")


def search_hit(url: str, title: str = "A related story", content: str = "", published: str | None = None) -> dict:

    return {
        "url": url,
        "title": title,
        "content": content,
        "engines": ["bing news"],
        "publishedDate": published,
    }


def answer(body: str = "Volunteers planted native trees in the valley [1].", **extra) -> dict:
    """What the writer's model returns, in the shape the prompt asks for."""

    result = {
        "title": "Un bosc torna a la vall",
        "subtitle": "Voluntaris hi han plantat arbres autòctons",
        "body": body,
        "metadata": {
            "slug": "Un bosc torna a la vall!",
            "seoDescription": "Voluntaris planten arbres autòctons a la vall.",
            "keywords": ["arbres", "voluntaris", "arbres"],
            "tags": ["medi ambient"],
            "topic": "Medi ambient",
        },
    }

    result.update(extra)

    return result


def published_lake(tmp_path, **kwargs):
    """A lake holding one published article; returns (lake, its reader id)."""

    lake = make_lake(tmp_path / "lake")

    publish(lake, kwargs.pop("url", ANALYSED_URL), **kwargs)

    return lake, reader_id(ANALYSED_URL)


def make_writer(
    lake,
    llm=None,
    search=None,
    extractor=None,
    repository=None,
    rated=(),
) -> DraftWriter:

    return DraftWriter(
        articles=AnalysedArticles(ReaderIndex(lake), lake),
        related=RelatedNewsFinder(
            search=search or FakeSearxngClient(results=[]),
            extractor=extractor or FakeExtractorService(),
            repository=(lambda: repository) if repository is not None else (lambda: FakeVectorRepository()),
            embeddings=ExplodingEmbeddings(),
            rated=RatedDomains(set(rated)),
        ),
        writer=ArticleWriter(llm or FakeLLMClient(answer())),
    )


SEPTEMBER = datetime(2026, 9, 1, 8, 0)
