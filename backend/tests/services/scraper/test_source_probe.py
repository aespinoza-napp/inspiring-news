import json

from src.models.core.news import News
from src.services.scraper.discovery import DiscoveryResult
from src.services.scraper.request_stats import Outcome, RequestStats
from src.services.scraper.source_probe import SourceProbe, SourceProbeResult, classify_source
from src.services.scraper.strategies.topic_pages import SectionPage, TopicPagesResult

from tests.builders.source_builder import build_source


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------


class FakeFeeds:

    def __init__(self, by_source: dict[str, list[str]], error: str | None = None):
        self.by_source = by_source
        self.error = error

    def run(self, source, topics=None) -> DiscoveryResult:

        urls = self.by_source.get(source.id, [])

        return DiscoveryResult(
            urls=list(urls),
            method="RSSDiscoveryStrategy" if urls else None,
            error=None if urls else (self.error or "RSSDiscoveryStrategy: no matching article links"),
        )


class FakeTopicPages:

    def __init__(self, by_source: dict[str, list[str]], homepage_error: str | None = None):
        self.by_source = by_source
        self.homepage_error = homepage_error

    def crawl(self, source, topics=None) -> TopicPagesResult:

        links = self.by_source.get(source.id, [])

        return TopicPagesResult(
            homepage_status=403 if self.homepage_error else 200,
            homepage_outcome="http_error" if self.homepage_error else "ok",
            homepage_error=self.homepage_error,
            sections=[SectionPage(url=f"{source.base_url}science/", advertised=True, status=200, links=links)] if links else [],
        )


class FakeExtractor:
    """Extracts every URL except the ones listed as failing, and records like the real one."""

    def __init__(self, stats, failing: dict[str, tuple[Outcome, int | None]]):
        self.stats = stats
        self.failing = failing
        self.extracted: list[str] = []

    def extract(self, source, url, thresholds=None, purpose="article"):

        self.extracted.append(url)

        if url in self.failing:
            outcome, status = self.failing[url]
            self.stats.record(url, outcome, purpose=purpose, source_id=source.id, status=status,
                              error=f"HTTP {status}" if status else outcome.value)
            return None

        self.stats.record(url, Outcome.OK, purpose=purpose, strategy="TrafilaturaStrategy", source_id=source.id)

        return News(source_id=source.id, url=url, title="A title", content="body " * 200, language="en")


class FakeSearch:

    def __init__(self, results: int):
        self.results = results
        self.queries = []

    def health(self, query, language=None):
        self.queries.append((query, language))
        return {"query": query, "ok": bool(self.results), "results": self.results,
                "engines": ["brave"] if self.results else [],
                "unresponsive": [] if self.results else [{"engine": "brave", "reason": "too many requests"}]}


def make_probe(feeds=None, topics=None, failing=None, sources=None, homepage_error=None, **kwargs):

    extractors = []

    def factory(stats):
        extractor = FakeExtractor(stats, failing or {})
        extractors.append(extractor)
        return extractor

    probe = SourceProbe(
        sources=sources or [build_source()],
        stats=kwargs.pop("stats", RequestStats()),
        feed_discovery=FakeFeeds(feeds or {}),
        topic_pages=FakeTopicPages(topics or {}, homepage_error=homepage_error),
        extractor_factory=factory,
        **kwargs,
    )

    return probe, extractors


def urls(prefix: str, n: int) -> list[str]:

    return [f"https://bbc.com/{prefix}/{i}/a-long-article-headline-here" for i in range(n)]


# ----------------------------------------------------------------------
# classify_source: the verdict alone
# ----------------------------------------------------------------------


def result(feed=0, topic=0, sample=(), homepage_error=None, feed_error=None) -> SourceProbeResult:

    return SourceProbeResult(
        source="bbc", name="BBC", language="en",
        feed_links=feed, topic_links=topic, homepage_error=homepage_error, feed_error=feed_error,
        sample=[{"ok": ok, "outcome": "ok" if ok else "http_error"} for ok in sample],
    )


def test_a_working_feed_whose_articles_extract_is_up():

    assert classify_source(result(feed=10, sample=[True, True, False]))[0] == "up"


def test_a_dead_feed_rescued_by_topic_pages_is_degraded_not_down():
    """National Geographic, RTVE and SINC on 2026-09-25: 404 feed, articles readable."""

    status, reason = classify_source(result(topic=100, sample=[True, True], feed_error="HTTP 404"))

    assert status == "degraded"
    assert "HTTP 404" in reason
    assert "100 links from topic pages" in reason


def test_links_that_never_extract_are_down():
    """El País on 2026-09-25: a working feed, and a 403 on every article."""

    status, reason = classify_source(result(feed=138, sample=[False, False, False]))

    assert status == "down"
    assert "http_error" in reason


def test_a_refused_homepage_and_no_feed_is_down():

    status, reason = classify_source(result(homepage_error="HTTP 401"))

    assert status == "down"
    assert "HTTP 401" in reason


def test_fewer_than_half_extracting_is_degraded():

    assert classify_source(result(feed=10, sample=[True, False, False]))[0] == "degraded"


# ----------------------------------------------------------------------
# SourceProbe.probe: one source end to end, over fakes
# ----------------------------------------------------------------------


def test_topic_page_links_the_feed_lacks_are_counted_as_extra():

    feed = urls("feed", 3)
    topic = [feed[0]] + urls("science", 4)

    probe, _ = make_probe(feeds={"bbc": feed}, topics={"bbc": topic})

    report = probe.probe(build_source(), per_source=4)

    assert report.feed_links == 3
    assert report.topic_links == 5
    assert report.extra_links == 4


def test_the_sample_alternates_feed_and_topic_page_links():

    feed = urls("feed", 3)
    topic = urls("science", 3)

    probe, extractors = make_probe(feeds={"bbc": feed}, topics={"bbc": topic})

    report = probe.probe(build_source(), per_source=4)

    assert extractors[0].extracted == [feed[0], topic[0], feed[1], topic[1]]
    assert [item["via"] for item in report.sample] == ["feed", "topic_page", "feed", "topic_page"]


def test_each_sampled_article_carries_why_it_failed():

    feed = urls("feed", 2)

    probe, _ = make_probe(feeds={"bbc": feed}, failing={feed[1]: (Outcome.HTTP_ERROR, 403)})

    report = probe.probe(build_source(), per_source=2)

    ok, refused = report.sample

    assert ok["ok"] is True and ok["strategy"] == "TrafilaturaStrategy" and ok["title"] is True
    assert refused["ok"] is False
    assert refused["outcome"] == "http_error"
    assert refused["status"] == 403


def test_probe_extractions_are_counted_in_the_shared_stats_as_probe():

    stats = RequestStats()

    probe, _ = make_probe(feeds={"bbc": urls("feed", 2)}, stats=stats)

    probe.probe(build_source(), per_source=2)

    [entry] = stats.snapshot()["domains"]

    assert entry["purposes"] == {"probe": 2}


def test_a_per_source_of_zero_checks_links_without_extracting():

    probe, extractors = make_probe(feeds={"bbc": urls("feed", 5)})

    report = probe.probe(build_source(), per_source=0)

    assert report.sample == []
    assert extractors[0].extracted == []


# ----------------------------------------------------------------------
# SourceProbe.run: the report, persisted, and the search check
# ----------------------------------------------------------------------


def test_the_report_totals_every_source_and_only_enabled_ones():

    sources = [
        build_source(id="bbc", base_url="https://bbc.com/"),
        build_source(id="rtve", base_url="https://rtve.es/", rss_url=None),
        build_source(id="off", base_url="https://off.com/", enabled=False),
    ]

    probe, _ = make_probe(
        sources=sources,
        feeds={"bbc": urls("feed", 2)},
        topics={"rtve": ["https://rtve.es/ciencia/2026-09-25/un-articulo-largo-de-verdad"]},
    )

    report = probe.run(per_source=2)

    assert [s["source"] for s in report["sources"]] == ["bbc", "rtve"]
    assert report["totals"]["up"] == 1
    assert report["totals"]["degraded"] == 1
    assert report["totals"]["extraLinks"] == 1


def test_the_report_survives_a_restart(tmp_path):

    path = tmp_path / "stats" / "source_probe.json"

    probe, _ = make_probe(feeds={"bbc": urls("feed", 1)}, path=path)
    probe.run(per_source=1)

    assert json.loads(path.read_text(encoding="utf-8"))["totals"]["sources"] == 1

    again, _ = make_probe(path=path)

    assert again.state()["report"]["totals"]["up"] == 1


def test_search_engines_are_checked_in_both_languages():

    search = FakeSearch(results=0)

    probe, _ = make_probe(feeds={"bbc": urls("feed", 1)}, search_client=search)

    report = probe.run(per_source=0)

    assert [language for _, language in search.queries] == ["en", "es"]
    assert report["search"][0]["unresponsive"] == [{"engine": "brave", "reason": "too many requests"}]


def test_only_one_probe_runs_at_a_time():

    probe, _ = make_probe()

    probe._running = True

    assert probe.start() is False
