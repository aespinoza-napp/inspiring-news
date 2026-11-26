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


def test_a_recorded_choice_is_the_editors_picks_and_its_round_is_kept_whole():
    """
    Since 2026-11-24 the editor can record up to five on /discover to
    compare with the AI's five, without sending anything; that choice is
    the editor's side, its own `blind` decides the mode, and the round is
    written out whole for git.
    """

    scores = {"r1": 9, "r2": 7, "r3": 2, "r4": 1}
    recorded = round_("r", proposed=["r1", "r2"], sent=["r4"], scores=scores)
    recorded["candidates"] = [{"url": url, "title": url.upper(), "image": f"https://cdn.example/{url}.jpg"} for url in sorted(scores)]
    recorded["personSelection"] = {
        "at": "2026-11-24T10:00:00", "urls": ["r1", "r3"], "blind": True,
        "shown": sorted(scores), "notes": {"r3": "underrated"},
        "reasons": {"r1": ["positive", "trending"], "r3": ["positive", "diversity"]},
    }
    recorded["photos"] = {"r1": {"image": "https://cdn.example/r1.jpg", "file": "0011223344556677.jpg"}}

    result = selection_experiment([recorded])

    [row] = result["rounds"]
    assert (row["mode"], row["editor"], row["final"], row["kept"]) == ("blind", "recorded", 2, 1)
    assert (row["precision"], row["recall"]) == (0.5, 0.5)
    assert row["kappa"] == 0.0

    [whole] = result["compared"]
    assert [c["url"] for c in whole["candidates"]] == ["r1", "r2", "r3", "r4"]
    first, _, third, _ = whole["candidates"]
    assert (first["person"], first["ai"], first["aiScore"], first["photo"]) == (True, True, 9, "0011223344556677.jpg")
    assert (third["person"], third["ai"], third["personNote"], third["image"]) == (True, False, "underrated", "https://cdn.example/r3.jpg")
    assert third["personReasons"] == ["positive", "diversity"]

    # r1 (positive, trending) was the AI's too; r3 (positive, diversity) was not.
    assert result["summary"]["blind"]["byReason"] == {
        "positive": {"picks": 2, "aiAlso": 1, "aiShare": 0.5},
        "trending": {"picks": 1, "aiAlso": 1, "aiShare": 1.0},
        "diversity": {"picks": 1, "aiAlso": 0, "aiShare": 0.0},
    }

    report = experiments.selection_report(result)
    assert "Kappa" in report and "| blind | trending | 1 | 1 |" in report


def test_a_choice_recorded_after_the_ais_proposal_is_assisted():

    later = round_("s", proposed=["s1"], sent=[], scores={"s1": 9, "s2": 1}, ai_started="2026-11-24T09:00:00")
    later["queued"] = None
    later["personSelection"] = {"at": "2026-11-24T10:00:00", "urls": ["s1"], "blind": False}

    [row] = selection_experiment([later])["rounds"]

    assert (row["mode"], row["editor"]) == ("assisted", "recorded")


def test_round_labels_come_from_a_choice_recorded_or_sent_and_never_from_a_round_without_one():

    sent = {"candidates": [{"url": "a"}, {"url": "b"}], "queued": {"urls": ["a"]}}
    not_sent = {"candidates": [{"url": "c"}], "queued": None}

    assert round_labels([sent, not_sent]) == {"a": True, "b": False}


def test_a_recorded_choice_labels_its_round_unsent_and_wins_over_what_was_sent():
    """
    Step 10's blind rounds are recorded on /discover and need not be sent
    (2026-11-24): the recorded choice over what was shown is the label,
    as the selection experiment reads it.
    """

    recorded = {
        "candidates": [{"url": u, "title": u.upper()} for u in ("p", "q", "r", "s")],
        "personSelection": {"urls": ["q"], "shown": ["p", "q", "r"], "blind": True},
        "queued": {"urls": ["p"]},
    }

    labels, titles, provenance = experiments.admission_labels([recorded])

    # s was never shown, so it was not passed over.
    assert labels == {"p": False, "q": True, "r": False}
    assert titles["q"] == "Q"
    assert (provenance["rounds"], provenance["recorded"], provenance["sent"]) == (1, 1, 0)


def test_not_for_us_is_a_no_anywhere_and_devastating_rounds_are_left_out():

    marked_only = {"candidates": [{"url": "m"}, {"url": "n"}], "rejected": {"m": {"reasons": ["off_topic"]}}}
    devastating = {"edition": "devastating", "candidates": [{"url": "d"}], "queued": {"urls": ["d"]}}
    elsewhere = {"candidates": [{"url": "n"}, {"url": "o"}], "queued": {"urls": ["n"]}}

    labels, _, provenance = experiments.admission_labels([marked_only, devastating, elsewhere])

    # m was marked in a round with no choice; n passed over there is not
    # labelled by it, and a pick in another round makes it True.
    assert labels == {"m": False, "n": True, "o": False}
    assert (provenance["rejected"], provenance["devastatingLeftOut"], provenance["roundsRead"]) == (1, 1, 3)


def cell(topic, impact, recall, not_chosen):
    return {"topicMin": topic, "impactMin": impact, "recall": recall, "notChosenAdmitted": not_chosen}


DEFAULTS = {"topicMin": 0.35, "impactMin": 0.3}


def test_the_starting_point_is_the_strictest_cell_keeping_95_percent_of_the_picks():

    grid = [
        cell(0.30, 0.10, 1.00, 0.90),
        cell(0.35, 0.20, 0.96, 0.60),
        cell(0.40, 0.20, 0.96, 0.60),   # as strict, but further from the defaults
        cell(0.45, 0.30, 0.80, 0.20),   # strictest, but loses a fifth of the picks
    ]

    point = experiments.starting_point(grid, DEFAULTS, labelled=120, chosen=25)

    assert point["proposed"] and point["keepsRecall"]
    assert (point["topicMin"], point["impactMin"]) == (0.35, 0.20)


def test_with_no_cell_keeping_95_percent_the_most_keeping_one_is_proposed_and_said_so():

    grid = [cell(0.35, 0.30, 0.90, 0.50), cell(0.40, 0.30, 0.90, 0.40), cell(0.45, 0.30, 0.70, 0.10)]

    point = experiments.starting_point(grid, DEFAULTS, labelled=120, chosen=25)

    assert (point["topicMin"], point["keepsRecall"]) == (0.40, False)


def test_no_starting_point_under_100_labelled_or_20_picks():

    grid = [cell(0.35, 0.30, 1.0, 0.5)]

    assert not experiments.starting_point(grid, DEFAULTS, labelled=99, chosen=30)["proposed"]
    assert not experiments.starting_point(grid, DEFAULTS, labelled=162, chosen=15)["proposed"]


def test_admission_reads_the_backends_rounds_and_enriches_only_what_a_choice_labels(monkeypatch, tmp_path):

    labelled = {"id": "a", "candidates": [{"url": "x", "title": "X"}, {"url": "y"}], "queued": {"urls": ["x"]}}
    unlabelled = {"id": "b", "candidates": [{"url": "z"}], "queued": None}
    asked = []

    monkeypatch.setattr(experiments, "http_backend", lambda backend: f"call:{backend}")
    monkeypatch.setattr(experiments, "load_rounds_from", lambda call: [labelled, unlabelled] if call == "call:http://b" else [])
    monkeypatch.setattr(experiments, "load_rounds", lambda folder: pytest.fail("read data/lake without --lake"))
    monkeypatch.setattr(experiments, "http_enrich", lambda backend: lambda url: asked.append(url) or enrich_entry([("Climate", 0.5)]))
    monkeypatch.setattr(experiments, "ENRICH_CACHE", tmp_path / "cache.jsonl")
    monkeypatch.setattr(experiments, "enriched", lambda urls, enrich: {url: {"url": url, **enrich(url)} for url in urls})
    monkeypatch.setattr(experiments, "write", lambda name, result, report: tmp_path)

    assert experiments.main(["admission", "--backend", "http://b"]) == 0
    assert sorted(asked) == ["x", "y"]


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
    # Of the two not chosen, weak is admitted at 0.35 (0.37 > 0.35) and
    # nothing at 0.40; no pick is lost at either.
    assert (loose["notChosenAdmitted"], strict["notChosenAdmitted"]) == (0.5, 0.0)
    assert (loose["picksLost"], strict["picksLost"]) == (0, 0)
    assert result["aucImpactScore"] == 1.0
    assert result["impactAuc"]["auc"] == 1.0 and result["topicAuc"]["auc"] == 1.0
    assert [row["url"] for row in result["highestNotChosen"]] == ["off", "weak"]
    assert [row["url"] for row in result["lowestChosen"]] == ["good"]
    # Three labelled, one pick: too few for the rule.
    assert not result["startingPoint"]["proposed"]
    assert "No starting point proposed yet" in experiments.admission_report(result)


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


def test_the_feedback_experiment_lowers_what_leans_to_the_rejected_on_other_days(monkeypatch):
    """
    src/evaluation/feedback_experiment.py on made-up rows: the bad lie toward
    one direction, the good toward another, on every day. Lowering by the
    lean must order the other days better than the story alone.
    """

    import numpy as np

    from src.evaluation import feedback_experiment as fe

    monkeypatch.setattr(fe, "DRAWS", 3)
    rng = np.random.default_rng(1)

    def row(day, hand, i):
        lean = {0: np.array([1.0, 0.0]), 1: np.array([0.5, 0.5]), 2: np.array([0.0, 1.0])}[hand]
        vector = np.concatenate([lean, rng.normal(0, 3.0, 30)])
        # The story part alone gets a third of them backwards.
        story = {0: -0.02, 1: 0.0, 2: 0.02}[hand] * (-1 if i % 3 == 0 else 1)
        return {"url": f"https://x/{day}/{hand}/{i}", "day": day, "hand": hand, "v": vector / np.linalg.norm(vector), "story": story}

    rows = [row(day, hand, i) for day, counts in (("6 Oct", (12, 6, 6)), ("9 Oct", (45, 10, 22)), ("13 Oct", (10, 6, 6)))
            for hand, n in enumerate(counts) for i in range(n)]

    result = fe.feedback_experiment(rows)
    way = result["oneWay"][0]

    assert way["aucLowered"]["0.5"][0] > way["aucStory"][0]
    assert len(way["nearestNeighbour"]) == len(fe.FLOORS) * 2
    assert [size["rejected"] for size in result["draws"]["sizes"]] == [3, 5, 10, 20, 40]
    assert "Lowered by 0.5" in fe.feedback_report(result)
