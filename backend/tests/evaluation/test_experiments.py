"""
The experiments' arithmetic on hand-built data: no network, no model,
nothing written outside tmp_path.
"""

import json

import pytest

from src.evaluation import experiments
from src.evaluation.experiments import (
    admission_experiment,
    auc,
    enriched,
    labelled_articles,
    round_labels,
    selection_experiment,
    topic_ok,
    topics_experiment,
)


def test_auc_is_the_share_of_positive_negative_pairs_ranked_right_ties_half():

    assert auc([3, 2], [1, 2]) == (1 + 1 + 1 + 0.5) / 4
    assert auc([1], [1]) == 0.5
    assert auc([], [1]) is None


def scored(url, score):
    return {"url": url, "score": score, "reason": None}


def round_(id_, proposed, sent, scores, ai_started="2026-10-05T10:00:00", queued_at="2026-10-05T11:00:00", blind=False):

    urls = sorted(scores)

    return {
        "id": id_,
        "groups": ["environment"],
        "candidates": [{"url": url} for url in urls],
        "aiSelection": {
            "status": "done",
            "startedAt": ai_started,
            "blind": blind,
            "picks": [scored(url, scores[url]) for url in proposed],
            "scored": [scored(url, scores[url]) for url in urls],
        },
        "queued": {"at": queued_at, "urls": sent},
    }


def test_selection_agreement_and_the_ais_auc_are_kept_apart_by_mode():

    assisted = round_("a", proposed=["u1", "u2"], sent=["u1", "u3"], scores={"u1": 9, "u2": 8, "u3": 2, "u4": 1})
    blind = round_("b", proposed=["v1"], sent=["v1"], scores={"v1": 9, "v2": 3}, ai_started="2026-10-05T12:00:00")
    unfinished = {"id": "c", "aiSelection": {"status": "running"}, "queued": {"urls": ["x"]}}

    result = selection_experiment([assisted, blind, unfinished])

    assert result["roundsUsable"] == 2

    [a, b] = result["rounds"]
    assert (a["mode"], a["precision"], a["recall"], a["jaccard"]) == ("assisted", 0.5, 0.5, round(1 / 3, 4))
    assert (b["mode"], b["precision"], b["recall"]) == ("blind", 1.0, 1.0)

    # Picked u1 (9), u3 (2) against skipped u2 (8), u4 (1): 3 of 4 pairs right.
    assert result["summary"]["assisted"]["aucAiScore"] == 0.75
    assert result["summary"]["blind"]["aucAiScore"] == 1.0


def test_round_labels_come_only_from_rounds_sent_to_analysis():

    sent = {"candidates": [{"url": "a"}, {"url": "b"}], "queued": {"urls": ["a"]}}
    not_sent = {"candidates": [{"url": "c"}], "queued": None}

    assert round_labels([sent, not_sent]) == {"a": True, "b": False}


def enrich_entry(topic_confidences, positive=0.6, constructiveness=0.6):

    return {
        "topics": [{"topic": name, "confidence": c} for name, c in topic_confidences],
        "sentiment": {
            "label": "positive", "positive": positive, "neutral": 0.2, "negative": 0.1,
            "polarity": 0.5, "subjectivity": 0.2, "confidence": 0.6, "emotionalIntensity": 0.1,
        },
        "quality": {
            "readability": 0.5, "objectivity": 0.5, "constructiveness": constructiveness,
            "inspirationalScore": 0.5, "hopefulness": 0.5, "societalImpact": 0.3, "novelty": 0.5,
        },
    }


def test_the_topic_steps_are_the_classifier_floor_and_the_filters_minimum():

    entry = enrich_entry([("Climate", 0.38)])

    assert topic_ok(entry, 0.35, floor=0.35)
    assert not topic_ok(entry, 0.40, floor=0.35)
    assert not topic_ok(entry, 0.30, floor=0.40)


def test_admission_is_replayed_per_threshold_pair_and_scored_against_the_editor():

    articles = {
        "good": enrich_entry([("Climate", 0.45)], positive=0.8, constructiveness=0.9),
        "weak": enrich_entry([("Climate", 0.37)], positive=0.2, constructiveness=0.0),
        "off": enrich_entry([("Climate", 0.20)]),
        "broken": {"url": "broken", "error": "403"},
    }
    labels = {"good": True, "weak": False, "off": False}

    result = admission_experiment(articles, labels, topic_mins=[0.35, 0.40], impact_mins=[0.0])

    assert (result["enriched"], result["failed"], result["noTopicAtAll"]) == (3, 1, 1)

    [loose, strict] = result["grid"]
    assert (loose["admitted"], loose["precision"], loose["recall"]) == (2, 0.5, 1.0)
    assert (strict["admitted"], strict["precision"], strict["recall"]) == (1, 1.0, 1.0)
    assert result["aucImpactScore"] == 1.0


def test_topics_are_scored_by_topic_group_and_by_what_the_pipeline_would_see():

    articles = {
        "a": enrich_entry([("Climate", 0.45), ("Energy", 0.44)]),
        "b": enrich_entry([("Energy", 0.30), ("Space", 0.20)]),
    }
    gold = {"a": "energy", "b": "energy", "missing": "space"}

    result = topics_experiment(articles, gold)

    assert result["articles"] == 2
    assert result["top1"]["mean"] == 0.5          # b's top is energy, a's is climate
    assert result["group"]["mean"] == 1.0         # both environment
    assert result["top3"]["mean"] == 1.0
    assert result["noTopic"]["mean"] == 0.5       # b has nothing at the 0.35 floor


def test_enrichment_is_cached_and_a_rerun_fetches_nothing(tmp_path):

    cache = tmp_path / "cache.jsonl"
    calls = []

    def fake_enrich(url):
        calls.append(url)
        if url == "bad":
            raise RuntimeError("403 Forbidden")
        return {"topics": [{"topic": "Climate", "confidence": 0.5}], "sentiment": {}, "quality": {}, "language": "en"}

    first = enriched(["a", "bad"], fake_enrich, cache)
    second = enriched(["a", "bad"], fake_enrich, cache)

    assert calls == ["a", "bad"]
    assert first == second
    assert "403" in second["bad"]["error"]
    assert len(cache.read_text(encoding="utf-8").splitlines()) == 2


def test_each_article_is_labelled_with_its_facts_most_common_topic(tmp_path):

    for number, (url, topic) in enumerate([("u", "energy"), ("u", "energy"), ("u", "climate"), ("v", "space"), ("w", "not-a-topic")], 1):
        (tmp_path / f"fact{number:03d}.json").write_text(json.dumps({"articleUrl": url, "topic": topic}), encoding="utf-8")

    assert labelled_articles(tmp_path) == {"u": "energy", "v": "space"}


def test_discovery_compares_each_setting_with_the_every_topic_baseline(monkeypatch):

    from src.services.scraper.discovery import DiscoveryResult, DiscoveryService

    from tests.builders.source_builder import build_source

    sources = [
        build_source(id="e360", groups=["environment"]),
        build_source(id="nasa", groups=["science"]),
    ]

    def run(self, source, topics=None):
        links = {"e360": ["https://e360.example/1", "https://e360.example/2"], "nasa": ["https://nasa.example/1"]}
        return DiscoveryResult(urls=links[source.id], method="fake")

    monkeypatch.setattr(DiscoveryService, "run", run)

    result = experiments.discovery_experiment([None, ["environment"]], per_source=1, sources=sources)

    [baseline, environment] = result["settings"]
    assert (baseline["sources"], baseline["links"], baseline["candidates"]) == (2, 3, 2)
    assert (environment["sources"], environment["links"], environment["candidates"]) == (1, 2, 1)
    assert environment["sourcesVsBaseline"] == 0.5 and environment["linksVsBaseline"] == pytest.approx(0.667)
