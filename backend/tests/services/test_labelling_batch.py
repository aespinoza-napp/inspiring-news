from datetime import datetime

from src.models.core.news import News
from src.models.core.source import NewsSource
from src.models.nlp.topic_prediction import TopicPrediction
from src.services.fact_checker.claim_selector import ClaimSelectionResult
from src.services.inference_client import InferenceUnavailable
from src.services.labelling_batch import BatchRequest, LabellingBatch
from src.services.scraper.discovery import DiscoveryResult
from src.services.scraper.request_stats import Purpose

from tests.factories import create_article, create_claim

LONG = " - long enough to be a real sentence and not a fragment."


def source(id, language="en", enabled=True):
    return NewsSource(
        id=id, name=id.upper(), base_url=f"https://{id}.example", language=language, enabled=enabled,
    )


class FakeDiscovery:

    def __init__(self, urls: dict[str, list[str]]):
        self.urls = urls

    def run(self, source, topics=None):
        return DiscoveryResult(urls=list(self.urls.get(source.id, [])), method="fake")


class FakeExtractor:

    def __init__(self, fail: set[str] = frozenset(), dates: dict[str, datetime] | None = None):
        self.fail = fail
        self.dates = dates or {}
        self.purposes = []

    def extract(self, source, url, thresholds=None, purpose=None):
        self.purposes.append(purpose)
        if url in self.fail:
            return None
        return News(
            source_id=source.id, url=url, title=f"Title of {url}", author="A. Writer",
            published_at=self.dates.get(url, datetime(2026, 9, 20)), language=source.language,
            content="Body text of the article.",
        )


class FakeEnrichment:
    """Topics per URL; claims named after the URL so they can be traced."""

    def __init__(self, topics: dict[str, str] | None = None, down: bool = False):
        self.topics = topics or {}
        self.down = down

    def process(self, news, thresholds=None):
        if self.down:
            raise InferenceUnavailable("inference/ is down")
        topic = self.topics.get(news.url, "Climate")
        return create_article(
            url=news.url,
            title=news.title,
            claims=[
                create_claim(text=f"{news.url} claim {i}{LONG}", confidence=0.5 + i / 10)
                for i in range(5)
            ] + [create_claim(text="Too short.", confidence=0.99)],
            topics=[TopicPrediction(topic=topic, confidence=0.7, probability=0.1)],
        )


class FakeSelector:

    def __init__(self, down: bool = False):
        self.down = down

    def select(self, claims, thresholds=None, context=None):
        if self.down:
            raise InferenceUnavailable("no embeddings")
        chosen = [c.model_copy(update={"anchor_score": 0.9 - i / 10}) for i, c in enumerate(claims[:4])]
        return ClaimSelectionResult(selected=chosen)


class FakeClaimExtractor:

    def process(self, text, language=None):
        return [
            create_claim(text=f"fallback low{LONG}", confidence=0.3),
            create_claim(text=f"fallback high{LONG}", confidence=0.9),
        ]


def batch(sources, urls, enrichment=None, selector=None, extractor=None):
    return LabellingBatch(
        sources=sources,
        extractor=extractor or FakeExtractor(),
        enrichment=enrichment or FakeEnrichment(),
        selector=selector or FakeSelector(),
        claim_extractor=FakeClaimExtractor(),
        discovery=FakeDiscovery(urls),
    )


def urls_for(*ids, n=3):
    return {i: [f"https://{i}.example/a{k}" for k in range(n)] for i in ids}


# ----------------------------------------------------------------------


def test_one_article_per_source_and_at_most_the_claims_asked_for():

    sources = [source(s) for s in "abcdef"]

    result = batch(sources, urls_for(*"abcdef")).run(
        BatchRequest(articles=4, claims_per_article=2, seed="2026-09-29")
    )

    articles = result["articles"]
    assert len(articles) == 4
    assert len({a["source"] for a in articles}) == 4
    assert all(1 <= len(a["claims"]) <= 2 for a in articles)
    assert all(c["selectedBy"] == "anchor" for a in articles for c in a["claims"])


def test_the_same_seed_proposes_the_same_articles():

    sources = [source(s) for s in "abcdef"]
    urls = urls_for(*"abcdef")

    one = batch(sources, urls).run(BatchRequest(articles=3, seed="2026-09-29"))
    two = batch(sources, urls).run(BatchRequest(articles=3, seed="2026-09-29"))
    other = batch(sources, urls).run(BatchRequest(articles=3, seed="2026-09-30"))

    pick = lambda r: [a["url"] for a in r["articles"]]
    assert pick(one) == pick(two)
    assert pick(one) != pick(other)


def test_urls_already_labelled_or_proposed_are_never_proposed_again():

    sources = [source("a")]
    urls = {"a": ["https://a.example/old", "https://a.example/new"]}

    result = batch(sources, urls).run(BatchRequest(
        articles=5,
        # A tracking parameter and a trailing slash do not make it new.
        exclude=["https://a.example/old/?utm_source=x"],
    ))

    assert [a["url"] for a in result["articles"]] == ["https://a.example/new"]


def test_languages_are_interleaved_so_one_cannot_fill_the_batch():

    sources = [source(f"en{i}", "en") for i in range(6)] + [source("es0", "es"), source("es1", "es")]

    result = batch(sources, urls_for(*(s.id for s in sources), n=1)).run(BatchRequest(articles=4))

    languages = [a["language"] for a in result["articles"]]
    assert languages.count("es") == 2


def test_a_language_filter_keeps_only_that_language():

    sources = [source("en0", "en"), source("es0", "es")]

    result = batch(sources, urls_for("en0", "es0")).run(BatchRequest(articles=5, languages=["es"]))

    assert {a["language"] for a in result["articles"]} == {"es"}


def test_articles_on_a_wanted_topic_come_first():

    sources = [source(s) for s in "abcd"]
    urls = urls_for(*"abcd", n=1)
    topics = {"https://d.example/a0": "Medicine"}

    # Two wanted, so all four sources are drawn as candidates (OVERSAMPLE).
    result = batch(sources, urls, enrichment=FakeEnrichment(topics)).run(
        BatchRequest(articles=2, prefer_topics=["medicine"], seed="2026-09-29")
    )

    assert result["articles"][0]["url"] == "https://d.example/a0"
    # Display name from the classifier, key for the labeller.
    assert result["articles"][0]["topic"] == "medicine"


def test_an_article_that_does_not_extract_is_reported_not_proposed():

    sources = [source("a"), source("b")]
    urls = urls_for("a", "b", n=1)

    result = batch(sources, urls, extractor=FakeExtractor(fail={"https://a.example/a0"})).run(
        BatchRequest(articles=5)
    )

    assert [a["source"] for a in result["articles"]] == ["b"]
    assert result["skipped"][0]["url"] == "https://a.example/a0"


def test_without_embeddings_claims_are_ranked_by_the_extractors_confidence():

    sources = [source("a")]

    result = batch(sources, urls_for("a", n=1), selector=FakeSelector(down=True)).run(BatchRequest())

    claims = result["articles"][0]["claims"]
    assert all(c["selectedBy"] == "confidence" for c in claims)
    # Highest confidence first, and the fragment is never proposed.
    assert claims[0]["text"].startswith("https://a.example/a0 claim 4")
    assert all("Too short" not in c["text"] for c in claims)


def test_with_inference_down_the_extractor_alone_still_proposes_claims():

    sources = [source("a")]

    result = batch(sources, urls_for("a", n=1), enrichment=FakeEnrichment(down=True)).run(BatchRequest())

    article = result["articles"][0]
    assert article["topic"] is None
    assert article["claims"][0]["text"].startswith("fallback high")


def test_articles_are_read_with_their_own_purpose_and_carry_what_the_form_needs():

    extractor = FakeExtractor()

    result = batch([source("a")], urls_for("a", n=1), extractor=extractor).run(
        BatchRequest(request_id="abc")
    )

    assert set(extractor.purposes) == {Purpose.LABELLING}
    article = result["articles"][0]
    assert article["publishedAt"] == "2026-09-20"
    assert article["author"] == "A. Writer"
    assert article["site"] == "a.example"
    assert result["requestId"] == "abc"


def test_disabled_sources_are_not_drawn():

    result = batch([source("a", enabled=False), source("b")], urls_for("a", "b")).run(BatchRequest())

    assert {a["source"] for a in result["articles"]} == {"b"}


def test_a_second_start_while_one_runs_is_refused():

    service = batch([source("a")], urls_for("a"))

    service._running = True

    assert service.start(BatchRequest()) is False


def test_recent_articles_come_before_old_ones_and_before_a_wanted_topic():
    """
    The older the article, the wider the gap between the evidence the
    annotator may use (what existed that day) and the web the system
    searches today.
    """

    sources = [source(s) for s in "abcd"]
    urls = urls_for(*"abcd", n=1)
    old = datetime(2022, 1, 25)
    dates = {u: old for u in ("https://a.example/a0", "https://b.example/a0", "https://c.example/a0")}
    # d is the only recent one; a is old but on a wanted topic.
    topics = {"https://a.example/a0": "Medicine"}

    result = batch(
        sources, urls, enrichment=FakeEnrichment(topics), extractor=FakeExtractor(dates=dates)
    ).run(BatchRequest(articles=2, prefer_topics=["medicine"], seed="2026-09-29"))

    assert [a["url"] for a in result["articles"]] == ["https://d.example/a0", "https://a.example/a0"]



# ----------------------------------------------------------------------
# The mission screen and the age limit, as discovery rounds have them
# ----------------------------------------------------------------------


class Screen:
    """Leaves out every URL containing one of `off`; records what it read."""

    def __init__(self, off=(), error=None):
        self.off = off
        self.error = error
        self.read = []

    def assess(self, candidates, exempt=None):

        from src.services.selection.mission_screen import Assessment, Verdict

        if self.error:
            raise self.error

        self.read.extend(candidates)

        return [
            Assessment(Verdict(off_mission="celebrity") if any(o in (c.title or "") for o in self.off) else None)
            for c in candidates
        ]


def test_what_the_screen_leaves_out_is_never_extracted():
    """2026-10-09: the batch drew the Martin Fierro radio nominees and an awards-night photo gallery."""

    extractor = FakeExtractor()
    sources = [source(s) for s in "abcd"]
    urls = {i: [f"https://{i}.example/premios-martin-fierro-nominados-radio", f"https://{i}.example/rescued-turtle-returns-to-sea-today"] for i in "abcd"}

    screen = Screen(off=("Premios martin fierro",))
    labelling = LabellingBatch(
        sources=sources, extractor=extractor, enrichment=FakeEnrichment(), selector=FakeSelector(),
        claim_extractor=FakeClaimExtractor(), discovery=FakeDiscovery(urls), screen=screen,
    )

    result = labelling.run(BatchRequest(articles=4, seed="2026-10-09"))

    assert all("martin-fierro" not in a["url"] for a in result["articles"])
    assert len(result["articles"]) == 4
    assert result["screen"]["status"] == "ok"
    assert {s["offMission"] for s in result["screened"]} == {"celebrity"}
    assert result["totals"]["screened"] == len(result["screened"]) > 0
    # Read by the title made from its slug, as a round reads a section page's link.
    assert any(c.title == "Premios martin fierro nominados radio" for c in screen.read)


def test_when_the_screen_cannot_run_the_batch_keeps_everything_and_says_so():

    labelling = LabellingBatch(
        sources=[source("a")], extractor=FakeExtractor(), enrichment=FakeEnrichment(), selector=FakeSelector(),
        claim_extractor=FakeClaimExtractor(), discovery=FakeDiscovery(urls_for("a")),
        screen=Screen(error=InferenceUnavailable("connection refused")),
    )

    result = labelling.run(BatchRequest(articles=1, seed="2026-10-09"))

    assert result["screen"]["status"] == "unavailable"
    assert result["screened"] == [] and len(result["articles"]) == 1


def test_the_batch_discovers_only_what_a_round_would_offer():
    """Its own discovery used to have no age limit: a Samsung how-to from August was in the 2026-10-09 batch."""

    from src.services.ingestion_service import MAX_CANDIDATE_AGE

    labelling = LabellingBatch(
        sources=[], extractor=FakeExtractor(), enrichment=FakeEnrichment(), selector=FakeSelector(),
        claim_extractor=FakeClaimExtractor(),
    )

    assert labelling.discovery.max_age == MAX_CANDIDATE_AGE
