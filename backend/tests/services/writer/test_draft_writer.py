"""
Writing a draft start to finish (src/services/writer/draft_writer.py),
over a real lake and a real DraftStore; search, fetches, Qdrant and the
model faked (tests/services/writer/writer_fakes.py).
"""

from datetime import datetime

import pytest

from src.models.fact_checker.fact_check import Verdict
from src.services.llms import LLMUnavailableError
from src.services.writer.draft_store import DraftBusy

from tests.services.fact_checker.fakes import FakeLLMClient, FakeSearxngClient
from tests.services.reader.reader_lake import BODY, checked
from tests.services.writer.writer_fakes import (
    ANALYSED_URL,
    FakeVectorRepository,
    answer,
    make_writer,
    published_lake,
)

RELATED_PAGE = "Schools across the region joined the replanting this autumn, the council said. " * 8


def start(writer, store, article_id):

    article = writer.find_article(article_id=article_id)
    draft = store.save(writer.new_draft(article, "ca", "Short."))

    return writer.start(store, draft.id, article, wait=True)


def test_the_article_is_found_by_id_or_url_and_completed_from_the_lake(tmp_path):

    lake, article_id = published_lake(tmp_path)
    writer = make_writer(lake)

    by_id = writer.find_article(article_id=article_id)
    by_url = writer.find_article(article_url=ANALYSED_URL + "?utm_source=newsletter")

    assert by_id == by_url
    assert by_id.body is None

    complete = writer.articles.complete(by_id)

    assert complete.body == BODY
    assert complete.embedding and len(complete.embedding) == 1024
    assert "https://rated.example/planting" in complete.pages


def test_an_article_the_reader_does_not_publish_is_not_found(tmp_path):

    lake, article_id = published_lake(tmp_path, verdict=Verdict.FALSE)

    assert make_writer(lake).find_article(article_id=article_id) is None
    assert make_writer(lake).find_article(article_id="0" * 16) is None


def test_a_draft_is_written_with_the_analysed_article_as_source_one(tmp_path, draft_store):

    lake, article_id = published_lake(tmp_path)
    llm = FakeLLMClient(answer(body="Voluntaris van plantar arbres [1], i el pla segueix [3]. Citació inventada [9]."))
    llm.model = "qwen2.5:7b-instruct"

    draft = start(make_writer(lake, llm=llm), draft_store, article_id)

    assert draft.busy is None and draft.error is None
    assert draft.sources[0].origin == "analysed" and draft.sources[0].url == ANALYSED_URL
    assert draft.sources[0].excerpt.startswith("Volunteers in the valley planted")
    assert draft.content.title == "Un bosc torna a la vall"
    assert "[9]" not in draft.content.body
    assert draft.model == "qwen2.5:7b-instruct"
    assert [revision.reason for revision in draft.revisions] == ["generated"]
    assert draft.revisions[0].model == "qwen2.5:7b-instruct"
    assert draft.metadata.slug == "un-bosc-torna-a-la-vall"
    assert draft.fact_checks[0].verdict == "TRUE"
    assert draft.fact_checks[0].source_urls == ["https://rated.example/planting"]


def test_an_empty_web_search_still_writes_from_the_corpus_and_the_analysed_article(tmp_path, draft_store):

    lake, article_id = published_lake(tmp_path)

    repository = FakeVectorRepository(hits=[
        ("https://corpus.example/schools-join", 0.88, "Schools join the replanting", RELATED_PAGE, datetime(2026, 9, 3)),
    ])

    search = FakeSearxngClient(results=[])
    llm = FakeLLMClient(answer())

    draft = start(make_writer(lake, llm=llm, search=search, repository=repository), draft_store, article_id)

    assert search.queries, "the web was asked"
    assert [(source.origin, source.url) for source in draft.sources] == [
        ("analysed", ANALYSED_URL),
        ("related", "https://corpus.example/schools-join"),
        ("evidence", "https://rated.example/planting"),
    ]
    assert draft.content.body

    # The model is told the web had nothing, so it does not overreach.
    _, prompt = llm.calls[0]
    assert "found nothing on this story" in prompt


def test_web_search_and_corpus_both_down_still_write_a_draft(tmp_path, draft_store):

    lake, article_id = published_lake(tmp_path)

    llm = FakeLLMClient(answer())

    draft = start(
        make_writer(
            lake,
            llm=llm,
            search=FakeSearxngClient(unavailable=True),
            repository=FakeVectorRepository(error=RuntimeError("already accessed by another instance")),
        ),
        draft_store,
        article_id,
    )

    assert draft.error is None
    assert [source.origin for source in draft.sources] == ["analysed", "evidence"]

    _, prompt = llm.calls[0]
    assert "Web search was unavailable" in prompt
    assert "No related news was found" in prompt


def test_an_unverified_claim_reaches_the_model_as_not_to_be_stated(tmp_path, draft_store):
    """
    End to end through the lake. A published article cannot carry a FALSE
    claim (worst-claim-wins withholds it from the reader); a claim the
    model judged FALSE with nothing to cite comes back UNVERIFIED, and is
    passed on as that. The FALSE rule itself: test_article_writer.py,
    test_a_false_claim_reaches_the_prompt_as_false_and_not_to_be_stated.
    """

    lake, article_id = published_lake(tmp_path, checks=[
        checked(),
        checked(claim="The wetland is the largest in Europe.", verdict=Verdict.UNVERIFIED, raw_verdict=Verdict.FALSE),
    ], verdict=Verdict.UNVERIFIED)

    llm = FakeLLMClient(answer())

    start(make_writer(lake, llm=llm), draft_store, article_id)

    _, prompt = llm.calls[0]

    line = next(line for line in prompt.splitlines() if "largest in Europe" in line)

    assert "verdict UNVERIFIED" in line
    assert "do not state it as fact" in line


def test_the_sources_are_saved_before_the_model_answers(tmp_path, draft_store):
    """A model that fails leaves the material visible, and the failure in `error`."""

    lake, article_id = published_lake(tmp_path)

    draft = start(make_writer(lake, llm=FakeLLMClient(LLMUnavailableError("connection refused"))), draft_store, article_id)

    assert draft.busy is None
    assert "could not be reached" in draft.error
    assert draft.sources[0].origin == "analysed"
    assert draft.revisions == []
    # The placeholder title stays: the analysed article's headline.
    assert draft.content.title == "Volunteers plant 40,000 trees"


def test_a_busy_draft_refuses_a_second_generation(tmp_path, draft_store):

    lake, article_id = published_lake(tmp_path)
    writer = make_writer(lake)

    article = writer.find_article(article_id=article_id)
    draft = draft_store.save(writer.new_draft(article, "en", ""))

    draft_store.claim(draft.id, "generating")

    with pytest.raises(DraftBusy):
        writer.start(draft_store, draft.id, article, wait=True)
