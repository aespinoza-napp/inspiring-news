"""
The rule the AVeriTeC figures rest on: nothing published from the claim's date
on reaches the model. A failure here means a run read its answer.
"""

from datetime import date, datetime

import pytest

from src.config.thresholds import PipelineThresholds
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.fact_checker.claim_selector import ArticleContext
from src.services.fact_checker.ranking.ranking_retrieval import EvidenceRanker
from src.services.fact_checker.retrieval import temporal
from src.services.fact_checker.retrieval.evidence_retriever import EvidenceRetriever

from tests.factories import create_claim
from tests.services.fact_checker.fakes import (
    FakeEmbeddingService,
    FakeEvidenceScraper,
    FakeSearchProvider,
    FakeVectorRetriever,
)

CUTOFF = date(2020, 10, 31)


def _page(url: str, published: datetime | None = None, title: str = "A page") -> Evidence:

    return Evidence(
        url=url,
        title=title,
        snippet="the claim's words",
        published_at=published,
        origin=EvidenceOrigin.WEB,
        domain=url.split("/")[2],
    )


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.politifact.com/factchecks/2020/oct/31/viral-image/fake/", date(2020, 10, 31)),
        ("https://dailycaller.com/2020/11/03/fact-check-sean-connery/", date(2020, 11, 3)),
        ("https://example.com/news/2020-11-03-a-story", date(2020, 11, 3)),
        ("https://example.com/story-20201103-a", date(2020, 11, 3)),
        # Month only: the page may be from any day, so it reads as the last.
        ("https://example.com/2020/11/a-story", date(2020, 11, 30)),
        ("https://example.com/about", None),
        # Numbers that are not dates.
        ("https://example.com/2020/99/a-story", None),
        ("https://example.com/article/1234567890", None),
        ("https://example.com/20209999", None),
        # A publisher's id that happens to read as a date still to come.
        ("https://www.sciencedirect.com/science/article/pii/S0010440X20300225", None),
    ],
)
def test_the_date_a_news_address_states(url, expected):

    assert temporal.date_in_url(url) == expected


def test_a_snapshot_is_dated_by_when_it_was_taken_not_by_its_page():

    url = "https://web.archive.org/web/20201029000000/https://example.com/2021/01/05/story"

    assert temporal.date_in_url(url) == date(2020, 10, 29)
    assert temporal.unarchived(url) == "https://example.com/2021/01/05/story"


@pytest.mark.parametrize(
    "page,expected",
    [
        (_page("https://a.example/x", datetime(2020, 10, 30)), temporal.BEFORE),
        # "Before the claim's date": the day itself is too late.
        (_page("https://a.example/x", datetime(2020, 10, 31)), temporal.LATE),
        (_page("https://a.example/x", datetime(2021, 1, 1)), temporal.LATE),
        (_page("https://a.example/2020/11/03/x"), temporal.LATE),
        (_page("https://a.example/x"), temporal.UNDATED),
        # Two dates that disagree: one late one is enough to refuse.
        (_page("https://a.example/2020/11/03/x", datetime(2020, 1, 1)), temporal.LATE),
    ],
)
def test_where_a_page_stands(page, expected):

    assert temporal.standing(page, CUTOFF) == expected


def test_an_undated_page_is_refused_unless_the_run_vouches_for_it():

    pages = [_page("https://a.example/x"), _page("https://b.example/y", datetime(2020, 1, 1))]

    kept, refused = temporal.within(pages, CUTOFF)

    assert [page.url for page in kept] == ["https://b.example/y"]
    assert [item.reason for item in refused] == [temporal.REASON_UNDATED]

    kept, refused = temporal.within(pages, CUTOFF, undated="keep")

    assert len(kept) == 2 and not refused


def test_a_late_page_is_refused_even_when_undated_pages_are_kept():

    kept, refused = temporal.within([_page("https://a.example/2021/01/05/x")], CUTOFF, undated="keep")

    assert not kept
    assert [item.reason for item in refused] == [temporal.REASON_LATE]


def test_a_reference_page_is_refused_whatever_date_it_carries():
    """Found live: Wikipedia's "Walmart", dated the day it was created, with today's text."""

    wikipedia = _page("https://en.wikipedia.org/wiki/Walmart", datetime(2001, 9, 12))

    assert temporal.standing(wikipedia, CUTOFF) == temporal.LIVING

    for undated in ("drop", "keep"):
        kept, refused = temporal.within([wikipedia], CUTOFF, undated=undated)
        assert not kept and [item.reason for item in refused] == [temporal.REASON_LIVING]

    assert temporal.without_late([wikipedia], CUTOFF)[1][0].reason == temporal.REASON_LIVING


def test_a_copy_of_a_reference_page_from_the_time_is_evidence():

    snapshot = _page("https://web.archive.org/web/20200101000000/https://en.wikipedia.org/wiki/Walmart")

    assert temporal.standing(snapshot, CUTOFF) == temporal.BEFORE

    late = _page("https://web.archive.org/web/20210101000000/https://en.wikipedia.org/wiki/Walmart")

    assert temporal.standing(late, CUTOFF) == temporal.LATE


@pytest.mark.parametrize("url", ["https://notwikipedia.org/x", "https://example.com/wikipedia.org"])
def test_only_the_site_itself_counts_as_a_reference_work(url):

    assert not temporal.is_living(url)


@pytest.mark.parametrize("url,title", [
    ("https://www.politifact.com/x", ""),
    ("https://factcheck.afp.com/x", ""),
    ("https://www.thequint.com/fit/fit-webqoof/having-millets", ""),
    ("https://www.usatoday.com/story/news/factcheck/x", ""),
    ("https://news.example/story", "Fact check: millets do not prevent coronavirus"),
    ("https://web.archive.org/web/20210101000000/https://snopes.com/x", ""),
])
def test_a_fact_check_is_known_by_its_site_address_or_title(url, title):

    assert temporal.looks_like_fact_check(url, title)


@pytest.mark.parametrize("url,title", [
    ("https://www.usatoday.com/story/news/x", "A story"),
    ("https://notpolitifact.com/x", ""),
    ("https://example.com/politifact.com", ""),
])
def test_ordinary_news_is_not_a_fact_check(url, title):

    assert not temporal.looks_like_fact_check(url, title)


def test_an_undated_fact_check_is_refused_even_when_undated_pages_are_kept():
    """Found live: the verdict itself, in the knowledge store, under another address."""

    page = _page("https://www.thequint.com/fit/having-millets-prevents-coronavirus")

    kept, refused = temporal.within(
        [page], CUTOFF, undated="keep",
        fact_check="https://fit.thequint.com/fit-webqoof/having-millets-prevents-coronavirus-boosts-immunity-fact-check",
    )

    assert not kept and [item.reason for item in refused] == [temporal.REASON_FACT_CHECK]


def test_a_fact_check_dated_before_the_claim_was_there_to_be_read():

    page = _page("https://www.politifact.com/x", datetime(2019, 1, 1))

    assert temporal.standing(page, CUTOFF) == temporal.BEFORE


@pytest.mark.parametrize("url,site", [
    ("https://fit.thequint.com/x", "thequint.com"),
    ("https://www.thequint.com/x", "thequint.com"),
    ("https://news.bbc.co.uk/x", "bbc.co.uk"),
    ("https://example.com.au/x", "example.com.au"),
    ("https://web.archive.org/web/20200101000000/https://fit.thequint.com/x", "thequint.com"),
])
def test_the_site_of_an_address(url, site):

    assert temporal.site_of(url) == site


def test_with_no_cutoff_nothing_is_touched():

    pages = [_page("https://a.example/2099/01/05/x")]

    assert temporal.within(pages, None) == (pages, [])
    assert temporal.without_late(pages, None) == (pages, [])


class _Provider(FakeSearchProvider):

    def __init__(self, pages):

        super().__init__()

        self.pages = pages

    def search(self, claim, thresholds=None, context=None, language=None, timings=None):

        return list(self.pages)


class _DatingScraper(FakeEvidenceScraper):
    """Fetching is how an undated page's date is found: here, from a table."""

    def __init__(self, dates):

        super().__init__()

        self.dates = dates
        self.fetched: list[str] = []

    def enrich(self, evidence, wait=None, timings=None):

        self.fetched += [item.url for item in evidence]

        return [
            item.model_copy(update={"published_at": self.dates.get(item.url) or item.published_at, "content": "text"})
            for item in evidence
        ]


def _retriever(pages, dates=None):

    scraper = _DatingScraper(dates or {})

    retriever = EvidenceRetriever(
        repository=None,
        search_provider=_Provider(pages),
        scraper=scraper,
        vector_retriever=FakeVectorRetriever(),
        embeddings=FakeEmbeddingService(),
    )

    return retriever, scraper


def _context(**extra):

    return ArticleContext(url="https://checker.example/fact-check", evidence_before=CUTOFF, **extra)


def test_the_retriever_gives_the_model_nothing_from_after_the_claim():

    pages = [
        _page("https://a.example/2020/11/03/the-verdict"),        # late by its address, never fetched
        _page("https://b.example/page", datetime(2021, 5, 1)),    # late by the search's date, never fetched
        _page("https://c.example/undated-then-late"),             # late once fetched
        _page("https://d.example/undated-forever"),               # no date at all
        _page("https://e.example/good", datetime(2020, 3, 1)),    # dated before
        _page("https://f.example/undated-then-good"),             # dated before once fetched
    ]

    retriever, scraper = _retriever(pages, {
        "https://c.example/undated-then-late": datetime(2020, 12, 1),
        "https://f.example/undated-then-good": datetime(2019, 2, 2),
    })

    result = retriever.retrieve(create_claim(text="A claim"), PipelineThresholds(), context=_context())

    assert sorted(item.url for item in result.kept) == ["https://e.example/good", "https://f.example/undated-then-good"]

    assert "https://a.example/2020/11/03/the-verdict" not in scraper.fetched
    assert "https://b.example/page" not in scraper.fetched

    reasons = {item.url: item.reason for item in result.rejected}

    assert reasons["https://a.example/2020/11/03/the-verdict"] == temporal.REASON_LATE
    assert reasons["https://c.example/undated-then-late"] == temporal.REASON_LATE
    assert reasons["https://d.example/undated-forever"] == temporal.REASON_UNDATED


def test_the_funnel_goes_on_down_the_ranking_for_replacements_but_not_forever():

    thresholds = PipelineThresholds(max_evidence_per_claim=2)

    pages = [_page(f"https://site{index}.example/page") for index in range(20)]

    retriever, scraper = _retriever(pages, {
        "https://site5.example/page": datetime(2020, 1, 1),
    })

    result = retriever.retrieve(create_claim(text="A claim"), thresholds, context=_context())

    # Never two dated pages found, so it went as far as it may and stopped.
    assert len(scraper.fetched) == 2 * temporal.FETCH_FACTOR
    assert len(result.kept) <= 1


def test_the_claims_own_fact_check_is_refused_also_as_an_archived_copy():

    fact_check = "https://checker.example/fact-check"

    pages = [
        _page(fact_check, datetime(2020, 1, 1)),
        _page(f"https://web.archive.org/web/20200101000000/{fact_check}"),
        _page("https://e.example/good", datetime(2020, 3, 1)),
    ]

    retriever, _ = _retriever(pages)

    result = retriever.retrieve(
        create_claim(text="A claim"),
        PipelineThresholds(),
        context=ArticleContext(
            url=f"https://web.archive.org/web/20201130144023/{fact_check}",
            evidence_before=CUTOFF,
        ),
    )

    assert [item.url for item in result.kept] == ["https://e.example/good"]


def test_without_a_cutoff_the_app_reads_todays_web_as_before():

    pages = [_page("https://a.example/2099/01/05/x"), _page("https://b.example/y")]

    retriever, _ = _retriever(pages)

    result = retriever.retrieve(
        create_claim(text="A claim"),
        PipelineThresholds(),
        context=ArticleContext(url="https://article.example/own"),
    )

    assert sorted(item.url for item in result.kept) == ["https://a.example/2099/01/05/x", "https://b.example/y"]


def test_recency_is_measured_from_the_claim_not_from_today():

    ranker = EvidenceRanker.__new__(EvidenceRanker)

    fresh_then = datetime(2020, 10, 30)

    assert ranker._recency_score(fresh_then, as_of=CUTOFF) > 0.9
    assert ranker._recency_score(fresh_then) < ranker._recency_score(fresh_then, as_of=CUTOFF)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Updated October 2, 2020 at noon", date(2020, 10, 2)),
        ("Updated Oct. 2nd 2020", date(2020, 10, 2)),
        ("Published 2 October 2020", date(2020, 10, 2)),
        ("modified: 2020-10-02", date(2020, 10, 2)),
        # A bare month is its first day: it says nothing against the middle of it.
        ("in November 2020", date(2020, 11, 1)),
    ],
)
def test_the_dates_a_text_states(text, expected):

    assert expected in temporal.dates_in_text(text)


@pytest.mark.parametrize("text", ["", None, "may 2", "In 2020 and 2021", "February 30, 2020", "January 5, 2999"])
def test_what_is_not_a_date_in_a_text(text):

    assert temporal.dates_in_text(text) == []


def _with_text(content: str, url: str = "https://example.com/a-page", published=None) -> Evidence:

    page = _page(url, published)

    page.content = content

    return page


def test_a_page_stating_a_later_date_is_refused_even_when_undated_pages_are_kept():
    # Mayo Clinic's page, 2026-11-05: nothing in its address, "updated" in its text.

    page = _with_text("Coronavirus: who is at risk. Updated January 18, 2022.")

    kept, refused = temporal.within([page], CUTOFF, undated="keep")

    assert kept == []
    assert refused[0].reason == temporal.REASON_LATE_IN_TEXT


def test_the_claims_own_day_in_the_text_counts_as_late():

    assert temporal.standing(_with_text("Reported on October 31, 2020."), CUTOFF) == temporal.LATE_IN_TEXT


def test_a_page_dated_in_time_is_still_refused_for_a_later_date_in_its_text():

    page = _with_text("Corrected on March 3, 2021.", published=datetime(2020, 1, 1))

    assert temporal.standing(page, CUTOFF) == temporal.LATE_IN_TEXT


def test_a_later_date_in_the_snippet_refuses_a_page_before_it_is_fetched():

    page = _page("https://example.com/a-page")

    page.snippet = "Jan 3, 2021 - what the page says"

    kept, refused = temporal.without_late([page], CUTOFF)

    assert kept == [] and refused[0].reason == temporal.REASON_LATE_IN_TEXT


def test_earlier_dates_in_the_text_change_nothing():

    assert temporal.standing(_with_text("On October 30, 2020 and in May 2019."), CUTOFF) == temporal.UNDATED


def test_a_snapshot_from_before_the_claim_may_name_a_date_to_come():

    snapshot = _with_text(
        "The election will be held on November 3, 2020.",
        url="https://web.archive.org/web/20200101000000/https://example.com/a-page",
    )

    assert temporal.standing(snapshot, CUTOFF) == temporal.BEFORE


def test_a_site_named_for_fact_checking_is_known_by_its_name():

    assert temporal.looks_like_fact_check("https://mediabiasfactcheck.com/left-action/")
