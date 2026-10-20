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


# ----------------------------------------------------------------------
# emphasis
# ----------------------------------------------------------------------


def test_the_bootstrapped_auc_is_the_same_number_as_the_pairwise_one():

    items = [(3, True), (2, True), (1, False), (2, False), (2, True), (0.5, False)]

    positives = [score for score, positive in items if positive]
    negatives = [score for score, positive in items if not positive]

    assert experiments._rank_auc(items) == pytest.approx(auc(positives, negatives))
    assert experiments._rank_auc([(1, True)]) is None


def candidate(url, impact, fit, same_story=None):

    found = {
        "url": url,
        "reading": {"nearestTopic": "research", "topic": 0.5, "nearestOff": "politics", "off": 0.45, "impact": impact, "groupFit": fit},
        "rank": {"score": 0.0, "record": 0.9, "reliability": 0.9},
    }

    if same_story:
        found["sameStoryAs"] = same_story

    return found


# A Science round: two science stories fully on topic, two very positive
# ones of other groups that still fit, and a second version of the first.
SCIENCE = [
    candidate("sci-a", 0.47, 0.12),
    candidate("sci-b", 0.46, 0.11),
    candidate("dog", 0.55, -0.03),
    candidate("owl", 0.54, -0.02),
    candidate("sci-a-again", 0.49, 0.12, same_story="sci-a"),
]

LABELS = {
    "sci-a": (1, ["science"]), "sci-b": (0, ["science"]), "dog": (2, ["health"]),
    "owl": (2, ["environment"]), "sci-a-again": (1, ["science"]),
}


def alignment(tmp_path):

    round_ = {"round": "r1", "groups": ["science"], "candidates": SCIENCE[:3], "reserve": SCIENCE[3:]}
    runs = {"runs": [{"run": run, "rounds": [round_]} for run in ("before", "iter4", "recheck")]}

    (tmp_path / "runs.json").write_text(json.dumps(runs), encoding="utf-8")
    (tmp_path / "labelled.json").write_text(json.dumps({"candidates": [
        {"url": url, "hand": hand, "belongsTo": groups, "kind": "article"} for url, (hand, groups) in LABELS.items()
    ]}), encoding="utf-8")

    return tmp_path


def test_a_recorded_round_is_reordered_by_the_rankings_own_code(tmp_path):

    from src.services.selection import ranking

    rounds, labels, provenance = experiments.load_alignment(alignment(tmp_path), extra=())

    # "before" recorded no group fit: left out.
    assert [r["run"] for r in rounds] == ["iter4", "recheck"]
    assert len(labels) == 5 and list(provenance.values()) == [5]

    positive_first = experiments.reordered(rounds[0], ranking.weights(0.0))
    topic_first = experiments.reordered(rounds[0], ranking.weights(0.9))

    assert [c["url"] for c in positive_first] == ["dog", "owl", "sci-a-again", "sci-b", "sci-a"]
    # The round's own story grouping holds; which version leads may change.
    assert [c["url"] for c in topic_first] == ["sci-a-again", "sci-b", "owl", "dog", "sci-a"]
    assert topic_first[-1]["sameStoryAs"] == "sci-a-again"


def test_the_emphasis_experiment_reports_every_setting_against_before(tmp_path):

    rounds, labels, provenance = experiments.load_alignment(alignment(tmp_path), extra=())

    result = experiments.emphasis_experiment(rounds, labels, (0.0, 1.0), provenance)

    last = result["settings"]["last"]

    assert [row["setting"] for row in last] == ["before", "emphasis", "chosen", "emphasis"]
    assert [row["emphasis"] for row in last] == [None, 0.0, 0.6, 1.0]
    assert last[0]["firstTwenty"] == {
        "shown": 10, "ofGroup": 6, "anotherGroup": 4, "notArticle": 0, "worthOffering": 8,
        "clearlyPositive": 4, "worthOfferingOfGroup": 4, "clearlyPositiveOfGroup": 0, "notWorthOffering": 2,
    }
    # Topic first, the score tells the round's group from another's perfectly here.
    assert last[3]["auc"]["ofGroup"]["auc"] == 1.0

    report = experiments.emphasis_report(result)

    assert "**0.60 (chosen)**" in report and "before (0.51 / 0.15 / 0.21 / 0.13)" in report


def probed(source, status, sample, language="en"):

    return {"source": source, "language": language, "status": status, "reason": "", "feedLinks": 10, "topicLinks": 4, "sample": sample}


def item(ok, strategy=None, outcome="ok", ms=100):

    return {"ok": ok, "strategy": strategy, "outcome": outcome, "ms": ms}


def test_source_health_joins_the_probe_with_time_to_reception_and_lines_up_the_weeks():

    probe = {
        "startedAt": "2026-10-20T12:22:06+00:00",
        "perSource": 2,
        "sources": [
            probed("bbc", "up", [item(True, "TrafilaturaStrategy", ms=100), item(True, "BeautifulSoupStrategy", ms=300)]),
            probed("el_pais", "degraded", [item(True, "TrafilaturaStrategy"), item(False, outcome="http_error")], "es"),
        ],
        "search": [{"language": "en", "ok": True, "results": 86, "engines": ["bing"], "unresponsive": [{"engine": "google", "reason": "access denied"}]}],
    }
    freshness = {"sources": [{"source": "bbc", "hours": {"reception": {"n": 3, "median": 6.5}}}], "totals": {"hours": {"reception": {"n": 3, "median": 6.5}}}}

    result = experiments.sources_experiment(probe, freshness)

    assert (result["totals"]["up"], result["totals"]["degraded"], result["totals"]["down"]) == (1, 1, 0)
    assert result["totals"]["extractionRate"] == 0.75
    assert result["totals"]["byStrategy"] == {"TrafilaturaStrategy": 2, "BeautifulSoupStrategy": 1}
    assert result["totals"]["failures"] == {"http_error": 1}
    assert result["search"][0]["unresponsive"] == ["google"]

    bbc, el_pais = result["sources"]
    assert (bbc["extracted"], bbc["medianMs"], bbc["receptionHours"], bbc["receptionN"]) == (2, 200, 6.5, 3)
    assert (el_pais["receptionHours"], el_pais["receptionN"]) == (None, 0)

    earlier = json.loads(json.dumps(result))
    earlier["probedAt"] = "2026-10-13T09:00:00+00:00"
    earlier["sources"][1]["status"] = "up"

    report = experiments.sources_report(result, [earlier])

    assert "| el_pais | es | **degraded** |" in report
    assert "| el_pais | up | degraded |" in report
    assert "## Week by week" in report
    assert "## Week by week" not in experiments.sources_report(result)
