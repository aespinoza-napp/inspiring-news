"""
The two editions (src/config/editions.py, docs/decisions/editions.md):
what the Devastating edition changes, and that it changes nothing for
a positive run.
"""

import numpy as np
import pytest

from src.config.editions import (
    ALL_TOPIC_KEYWORDS_ES,
    ALL_TOPICS,
    EDITIONS,
    edition_of_topic,
    group_names_of,
    groups_of,
    known_edition,
    topics_of,
)
from src.config.thresholds import PipelineThresholds, ThresholdOverrides
from src.config.topics import DEVASTATING_TOPICS, TOPICS
from src.models.core.source import NewsSource
from src.processors.nlp.classifier import TopicClassifier
from src.services.admission.admission_filter import AdmissionFilter
from src.services.admission.devastation import DevastationScorer
from src.services.ingestion_service import IngestionService, topics_for
from src.services.scraper.strategies.rss import edition_of_topics, off_mission
from src.services.selection.ai_selector import DEFINITION, DEVASTATING_DEFINITION, definition, prompt
from src.services.selection.mission_screen import (
    DEVASTATING_IMPACT,
    DEVASTATING_OFF_MISSION,
    IMPACT,
    OFF_MISSION,
    Candidate,
    MissionScreen,
)
from src.services.writer.article_writer import (
    CLOSED_WORLD_RULES,
    SAFE_MESSAGING,
    SYSTEM_PROMPT,
    system_prompt,
    with_safe_messaging,
)
from src.services.writer.rewriter import REWRITE_SYSTEM_PROMPT, rewrite_system_prompt
from tests.factories import create_article
from tests.services.fact_checker.fakes import FakeEmbeddingService


# ----------------------------------------------------------------------
# The labels
# ----------------------------------------------------------------------


def test_the_two_editions_share_no_topic_id():
    """ALL_TOPICS finds either edition's topic by id: an id in both would hide one."""

    assert not set(TOPICS) & set(DEVASTATING_TOPICS)
    assert len(ALL_TOPICS) == len(TOPICS) + len(DEVASTATING_TOPICS)


@pytest.mark.parametrize("edition", EDITIONS)
def test_every_topic_of_an_edition_is_in_exactly_one_of_its_groups(edition):

    grouped = [topic for topics in groups_of(edition).values() for topic in topics]

    assert sorted(grouped) == sorted(topics_of(edition))
    assert set(group_names_of(edition)) == set(groups_of(edition))


def test_every_devastating_topic_has_spanish_feed_words():
    """Spanish feeds are filtered by these when a run is narrowed (rss._spanish_keywords_for)."""

    for topic in DEVASTATING_TOPICS:
        assert ALL_TOPIC_KEYWORDS_ES.get(topic), topic


def test_the_labels_asked_for_include_the_ones_in_the_request():

    assert {"Terrorism", "Racism", "Mass Killings", "Suicide & Self-harm"} <= {
        topic.name for topic in DEVASTATING_TOPICS.values()
    }


def test_an_unknown_edition_is_refused_and_none_is_positive():

    assert known_edition(None) == "positive"

    with pytest.raises(ValueError):
        known_edition("cheerful")

    with pytest.raises(ValueError):
        ThresholdOverrides(edition="cheerful")


def test_a_run_is_positive_unless_it_says_otherwise():

    assert PipelineThresholds().edition == "positive"
    assert PipelineThresholds.resolve(ThresholdOverrides(edition="devastating")).edition == "devastating"


def test_the_edition_is_recorded_as_an_override_only_when_it_is_one():

    assert "edition" not in PipelineThresholds().overridden_from_defaults()
    assert PipelineThresholds(edition="devastating").overridden_from_defaults()["edition"] == "devastating"


def test_the_two_editions_cache_apart(tmp_path):
    """The analysis cache keys on every threshold: a positive analysis is never served to a devastating run."""

    from src.services.analysis_cache import AnalysisCache

    cache = AnalysisCache(directory=tmp_path)
    url = "https://example.com/story"

    assert cache._path(url, PipelineThresholds()) != cache._path(url, PipelineThresholds(edition="devastating"))


# ----------------------------------------------------------------------
# The classifier
# ----------------------------------------------------------------------


@pytest.fixture
def fresh_caches(monkeypatch):

    monkeypatch.setattr(TopicClassifier, "_topic_embeddings", None)
    monkeypatch.setattr(TopicClassifier, "_keyword_embeddings", None)


def test_the_classifier_labels_with_the_runs_edition_only(fresh_caches):

    classifier = TopicClassifier(threshold=-1.0, embedding_service=FakeEmbeddingService())

    positive = {prediction.topic for prediction in classifier.process("A bombing in the city centre.")}
    devastating = {
        prediction.topic
        for prediction in classifier.process("A bombing in the city centre.", edition="devastating")
    }

    assert positive and positive <= {topic.name for topic in TOPICS.values()}
    assert devastating and devastating <= {topic.name for topic in DEVASTATING_TOPICS.values()}


def test_the_devastating_labels_are_embedded_only_when_first_asked_for(fresh_caches):

    TopicClassifier(threshold=-1.0, embedding_service=FakeEmbeddingService())

    assert set(TopicClassifier._topic_embeddings) == {"positive"}


# ----------------------------------------------------------------------
# Admission
# ----------------------------------------------------------------------


def _bleak(article):

    article.sentiment.negative = 0.85
    article.sentiment.positive = 0.05
    article.sentiment.emotional_intensity = 0.7
    article.quality.hopefulness = 0.05
    article.quality.inspirational_score = 0.05
    article.quality.constructiveness = 0.1
    article.quality.societal_impact = 0.9

    return article


def test_a_bleak_story_of_wide_harm_clears_the_devastation_gate():

    article = _bleak(create_article())

    result = DevastationScorer().score(article.sentiment, article.quality, PipelineThresholds(edition="devastating"))

    assert result.passed
    assert result.score > 0.5


def test_a_hopeful_story_does_not_clear_it():

    article = create_article()

    result = DevastationScorer().score(article.sentiment, article.quality, PipelineThresholds(edition="devastating"))

    assert not result.passed
    assert "Not negative enough" in result.reasons
    assert "Too hopeful" in result.reasons


def test_admission_asks_for_the_tone_of_the_runs_edition(repository):

    gate = AdmissionFilter(repository)
    hopeful = create_article()

    assert gate.admit(hopeful).positive_ok

    turned_away = gate.admit(hopeful, PipelineThresholds(edition="devastating"))

    assert not turned_away.positive_ok
    assert turned_away.edition == "devastating"
    assert "not_devastating" in turned_away.reason


def test_the_validated_event_says_which_edition_judged(repository):

    events = []

    AdmissionFilter(repository).admit(
        _bleak(create_article()),
        PipelineThresholds(edition="devastating"),
        on_phase=lambda phase, data: events.append((phase, data)),
    )

    validated = next(data for phase, data in events if phase == "validated")

    assert validated["edition"] == "devastating"
    assert validated["positiveOk"]


# ----------------------------------------------------------------------
# Discovery and selection
# ----------------------------------------------------------------------


def test_crime_sections_are_off_mission_only_for_the_positive_edition():

    url = "https://www.elpais.com/sucesos/2026-10-30/a-story.html"

    assert off_mission(url)
    assert not off_mission(url, "devastating")

    # Sport stays off for both.
    assert off_mission("https://www.elpais.com/deportes/2026-10-30/a-match.html", "devastating")


def test_discovery_tells_the_edition_from_the_topic_ids_it_is_handed():

    assert edition_of_topics(["terrorism", "war"]) == "devastating"
    assert edition_of_topics(["climate"]) == "positive"
    assert edition_of_topics([]) == "positive"
    assert edition_of_topic("racism") == "devastating"


def test_a_devastating_group_is_its_own_topics():

    assert topics_for(["violence"], "devastating") == ["terrorism", "mass_killings", "war"]
    assert topics_for(None, "devastating") == list(DEVASTATING_TOPICS)
    assert topics_for(["health"]) == ["medicine", "mental_health", "nutrition", "fitness", "public_health"]


def _source(id: str, groups: list[str], devastating_groups: list[str] | None = None, **extra) -> NewsSource:

    return NewsSource(
        id=id,
        name=id,
        base_url=f"https://{id}.example",
        rss_url=f"https://{id}.example/rss",
        language="en",
        groups=groups,
        devastating_groups=devastating_groups or [],
        **extra,
    )


def _sources() -> IngestionService:

    return IngestionService(
        sources=[
            _source("general", ["society"], ["violence", "hate"]),
            _source("science_desk", ["science"]),
            _source("good_news", ["society", "culture"], positive_editorial=True),
            _source("rights_watch", [], ["hate", "abuse_of_power"]),
        ],
        lake=None,
    )


def test_each_edition_reads_only_the_sources_that_name_its_groups():
    """NASA, Nature and Mongabay were read for Terrorism when the edition took every general outlet."""

    service = _sources()

    assert [s.id for s in service.sources_for(edition="devastating")] == ["general", "rights_watch"]
    assert [s.id for s in service.sources_for(["violence"], edition="devastating")] == ["general"]
    assert [s.id for s in service.sources_for(["abuse_of_power"], edition="devastating")] == ["rights_watch"]

    # A Devastating-only source is never the positive edition's.
    assert [s.id for s in service.sources_for()] == ["general", "good_news", "science_desk"]
    assert [s.id for s in service.sources_for(["society"])] == ["general", "good_news"]


def test_a_source_names_only_known_devastating_groups():

    with pytest.raises(ValueError):
        _source("x", [], ["violence", "sport"])

    assert _source("x", ["society"], ["hate"]).groups_in("devastating") == ["hate"]
    assert _source("x", ["society"], ["hate"]).groups_in("positive") == ["society"]


def test_every_devastating_group_has_sources_configured():

    from pathlib import Path

    from src.config.topics import DEVASTATING_TOPIC_GROUPS
    from src.repositories.source_repository import SourceRepository

    sources = Path(__file__).resolve().parents[1] / "data" / "sources"
    service = IngestionService(sources=SourceRepository(str(sources)).list(), lake=None)

    for group in DEVASTATING_TOPIC_GROUPS:
        assert len(service.sources_for([group], edition="devastating")) >= 3, group


def test_a_source_of_only_devastating_groups_needs_no_keyword_for_them():
    """Human Rights Watch's every item is on its groups: no keyword has to show it."""

    from src.services.scraper.strategies.rss import covers_only

    rights = _source("rights_watch", [], ["hate", "abuse_of_power"])

    assert covers_only(rights, set(topics_for(["hate", "abuse_of_power"], "devastating")))
    assert not covers_only(rights, set(topics_for(["hate"], "devastating")))


def _axis(size: int, index: int) -> np.ndarray:

    vector = np.zeros(size)
    vector[index] = 1.0

    return vector


class _Embeddings:
    """Every description on its own axis; a candidate on the axis named for it."""

    def __init__(self, nearest: dict[str, str]):
        self.nearest = nearest
        self.labels: list[str] = []

    def encode_many(self, texts):

        texts = list(texts)

        if not self.labels:
            self.labels = [text.strip().split("\n", 1)[0] for text in texts]
            return np.array([_axis(len(texts), i) for i in range(len(texts))])

        return np.array([_axis(len(self.labels), self.labels.index(self.nearest[text])) for text in texts])


def test_the_devastating_screen_keeps_harm_and_leaves_out_good_news():

    attack = "Gunman kills twelve at a market"
    rescue = "Volunteers rescue a whole village's dogs"

    screen = MissionScreen(
        embedding_service=_Embeddings({
            attack: DEVASTATING_TOPICS["mass_killings"].name,
            rescue: DEVASTATING_OFF_MISSION["good_news"][0],
        }),
        edition="devastating",
    )

    kept, dropped = screen.screen([Candidate(title=attack, summary=None), Candidate(title=rescue, summary=None)])

    assert kept is None
    assert dropped.off_mission == "good_news"


def test_a_death_is_the_devastating_editions_story_not_an_obituary():

    headline = Candidate(title="Former minister dies aged 86", summary=None, language="en")

    positive = MissionScreen(embedding_service=_Embeddings({}))

    assert positive.screen([headline])[0].off_mission == "obituary"

    # Read rather than dropped by its headline: the embeddings decide.
    devastating = MissionScreen(
        embedding_service=_Embeddings({"Former minister dies aged 86": DEVASTATING_TOPICS["disasters"].name}),
        edition="devastating",
    )
    assert devastating.screen([headline]) == [None]


def test_a_screen_makes_its_other_editions_sibling_once():

    screen = MissionScreen(embedding_service=_Embeddings({}))
    sibling = screen.sibling("devastating")

    assert sibling.edition == "devastating"
    assert sibling.embedding_service is screen.embedding_service
    assert sibling.off_mission is DEVASTATING_OFF_MISSION and sibling.impact is DEVASTATING_IMPACT
    assert screen.sibling("positive") is screen
    assert screen.off_mission is OFF_MISSION and screen.impact is IMPACT

    service = IngestionService(sources=[], lake=None, screen=screen)
    assert service.screen_for("devastating") is service.screen_for("devastating")
    assert service.screen_for("positive") is screen


def test_the_ai_selection_asks_each_edition_its_own_question():

    assert definition() .startswith(DEFINITION)
    assert definition("devastating").startswith(DEVASTATING_DEFINITION)
    assert "checkable" in DEVASTATING_DEFINITION

    listed = prompt([{"url": "u", "title": "t"}], ["violence", "hate"], "devastating")
    assert "Chosen topics: Violence, Hate." in listed


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------


def test_the_positive_prompts_are_unchanged_by_the_editions():

    assert SYSTEM_PROMPT == system_prompt("positive")
    assert REWRITE_SYSTEM_PROMPT == rewrite_system_prompt("positive")
    assert "Inspiring News" in SYSTEM_PROMPT


@pytest.mark.parametrize("make", [system_prompt, rewrite_system_prompt])
def test_the_devastating_voice_keeps_every_closed_world_rule(make):
    """The irony is the narrator's: the rules that hold a fact to its source are word for word the same."""

    prompt_text = make("devastating")

    assert CLOSED_WORLD_RULES in prompt_text
    assert "Devastating News" in prompt_text
    assert "narcissistic" in prompt_text
    assert "Never at the victims" in prompt_text
    assert "Suicide and self-harm" in prompt_text


def test_a_devastating_story_about_suicide_ends_with_a_route_to_help_once():

    body = "The figures rose again this year [1]."

    once = with_safe_messaging(body, "es", "devastating", "Suicide rates climb")

    assert once.endswith(SAFE_MESSAGING["es"])
    assert with_safe_messaging(once, "es", "devastating", "Suicide rates climb") == once


def test_no_help_line_where_it_does_not_belong():

    body = "The figures rose again this year [1]."

    assert with_safe_messaging(body, "en", "devastating", "A bombing in the capital") == body
    assert with_safe_messaging(body, "en", "positive", "Suicide prevention works") == body


def test_a_draft_is_written_in_the_edition_its_article_was_analysed_in():

    from src.services.writer.analysed_article import AnalysedArticle
    from src.services.writer.draft_writer import edition_of_article

    def article(topic):
        return AnalysedArticle(
            id="0123456789abcdef", url="https://example.com/a", headline="h", lead="l",
            language="en", topic=topic, published_at=None, source_name="Example", domain="example.com",
        )

    assert edition_of_article(article("Terrorism")) == "devastating"
    assert edition_of_article(article("Climate")) == "positive"
    assert edition_of_article(article(None)) == "positive"


def test_an_article_url_ending_in_an_id_is_still_a_headline():
    """DW Español's ".../varios-petroleros-arden-en-ormuz/a-79803780": every one was dropped."""

    from src.services.scraper.strategies.rss import _headline_slug

    assert _headline_slug("/es/varios-petroleros-arden-en-ormuz-tras-chocar/a-79803780")
    assert _headline_slug("/noticias/asi-se-hace-autentico-bacalao/17174859.shtml")
    assert not _headline_slug("/es/a-79803780")
    assert not _headline_slug("/es/noticias/123")


# ----------------------------------------------------------------------
# The review judges the voice by the draft's edition
# ----------------------------------------------------------------------


def test_the_review_asks_a_devastating_draft_for_its_own_voice():
    """
    The review asked every draft for "Constructive and hopeful", so the
    rewrite stage, fixing what it found, turned the narrator back into
    Inspiring's voice.
    """

    from src.services.corrector.draft_reviewer import REVIEW_SYSTEM_PROMPT, review_system_prompt

    devastating = review_system_prompt("devastating")

    assert review_system_prompt() == REVIEW_SYSTEM_PROMPT
    assert "Inspiring" not in devastating
    assert "Constructive and hopeful" not in devastating
    assert "NEVER on victims" in devastating
    # Everything that holds a fact to its source is the same text.
    assert REVIEW_SYSTEM_PROMPT.split("- seo:")[0].split("- title:")[1] in devastating


def test_the_copy_editor_keeps_the_devastating_voice():

    from src.services.corrector.draft_reviewer import correction_system_prompt, edits_system_prompt

    for make in (correction_system_prompt, edits_system_prompt):
        prompt_text = make("es", "devastating")
        assert "Devastating News" in prompt_text
        assert "constructive news register" not in prompt_text
        assert "Add no facts" in prompt_text

    assert "Inspiring" in correction_system_prompt("es")


# ----------------------------------------------------------------------
# A Devastating run reaches the lake, the reader and the writer
# ----------------------------------------------------------------------


def test_a_run_with_a_non_numeric_override_starts_its_lake_record(tmp_path):
    """
    The lineage took numbers only: every Devastating run failed to start
    its record ("edition: Input should be a valid integer"), so none was
    stored, published or writable - silently, as storage is fail-soft.
    """

    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))

    run = lake.start_run(
        "https://example.com/a",
        PipelineThresholds(
            edition="devastating",
            query_kinds=("anchor",),
            second_look_enabled=not PipelineThresholds().second_look_enabled,
            anchor_claims_max=7,
        ),
    )

    assert run.threshold_overrides["edition"] == "devastating"
    assert run.threshold_overrides["query_kinds"] == ["anchor"]
    assert isinstance(run.threshold_overrides["second_look_enabled"], bool)
    assert run.threshold_overrides["anchor_claims_max"] == 7
    assert isinstance(run.threshold_overrides["anchor_claims_max"], int)


def test_a_devastating_analysis_is_published_and_can_be_written_from(tmp_path):
    """From analysis to the Write step: stored, on the reader's Devastating feed, found by the writer."""

    from datetime import datetime
    from unittest.mock import Mock

    from src.models.core.news import News
    from src.models.nlp.topic_prediction import TopicPrediction
    from src.repositories.datalake_repository import DataLakeRepository
    from src.repositories.lake_backend import JsonFileLakeBackend
    from src.services.analysis_service import AnalysisService
    from src.services.reader.index import ReaderIndex
    from src.services.writer.analysed_article import AnalysedArticles
    from src.services.writer.draft_writer import edition_of_article

    url = "https://www.amnesty.org/en/latest/news/2026/10/cambodia-security-companies/"

    news = News(
        source_id="amnesty", url=url, title="Cambodia: security companies enabled slavery",
        published_at=datetime(2026, 10, 29), content="Survivors described forced labour and abuse.",
    )
    article = create_article(
        url=url,
        title=news.title,
        topics=[TopicPrediction(topic="Human Rights Abuses", confidence=0.7, probability=0.5)],
    )

    extractor = Mock()
    extractor.extract.return_value = news
    enrichment = Mock()
    enrichment.process.return_value = article
    admission = Mock()
    admission.admit.return_value = Mock(passed=True, topic_ok=True, positive_ok=True, duplicate=False, impact_score=0.7, impact_reasons=[])

    lake = DataLakeRepository(backend=JsonFileLakeBackend(tmp_path))
    cache = Mock()
    cache.get.return_value = None

    result = AnalysisService(
        fact_checker=Mock(), extractor=extractor, enrichment_pipeline=enrichment,
        cache=cache, lake=lake, admission=admission,
    ).analyze(url, thresholds=PipelineThresholds(edition="devastating"))

    assert result["storage"]["publishable"]

    index = ReaderIndex(lake)
    feed = index.feed(edition="devastating")

    assert feed["total"] == 1
    assert index.feed(edition="positive")["total"] == 0

    found = AnalysedArticles(index, lake).find(article_url=url)

    assert found is not None
    assert edition_of_article(found) == "devastating"
