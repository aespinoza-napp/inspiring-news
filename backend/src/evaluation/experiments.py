"""
Experiments on the stages before the fact-check: discovery, selection,
admission and the topic classifier. The harness (src/evaluation/cli.py)
measures verdicts; these measure what decides which articles get one.

    cd backend
    uv run python -m src.evaluation.experiments discovery [--group environment --group health,science] [--per-source 3]
    uv run python -m src.evaluation.experiments selection
    uv run python -m src.evaluation.experiments blind-ai --round <round id>
    uv run python -m src.evaluation.experiments admission [--backend http://127.0.0.1:8000] \
        [--topic-min 0.30,0.35,0.40,0.45] [--impact-min 0.10,0.20,0.25,0.30]
    uv run python -m src.evaluation.experiments topics [--backend http://127.0.0.1:8000]
    uv run python -m src.evaluation.experiments emphasis [--emphasis 0,0.3,0.6,1]

Each writes `result.json` and `report.md` to
`data/evaluation/experiments/<name>/<UTC time>/` and prints the report.

What each costs, and what it needs:

- **discovery** reads every source's feed or section pages for each
  topic-group setting it is given, and for no setting (the baseline):
  real network, no model, nothing stored. RQ: how much does narrowing to
  topics save, and what does it still find?
- **selection** only reads the candidate rounds recorded by /discover
  (`data/lake/stats/selection/`): how far the editor's final picks agree
  with the AI's proposal, and how well the AI's score separates what was
  picked from what was not.
- **blind-ai** runs the AI selection on a round the editor has already
  sent to analysis, so the agreement is measured without the editor
  having seen the AI's picks first (an anchored editor agrees more).
  Needs the LLM.
- **admission** sends every candidate of the recorded rounds (or every
  labelled fact's article, `--articles facts`) through the running
  backend's POST /enrich once - cached, so a re-run fetches nothing - and
  then replays the topic filter and the positive-impact gate over a grid
  of thresholds offline, with the pipeline's own classes. Where the
  editor chose among candidates, their choice is the label. Duplicate
  detection is left out: it depends on what the vector store held at the
  time. Needs the stack (inference/).
- **topics** compares the classifier's topics for each labelled fact's
  article with the topic the annotator gave it: the same /enrich cache.
- **emphasis** re-scores every candidate of the 2026-10-09 alignment
  rounds (data/evaluation/experiments/alignment/), shown or in reserve,
  at several topic emphases, with the ranking's own functions, from the
  readings the rounds recorded: nothing is embedded or fetched. RQ: how
  much does weighing the topic over positive impact change what a round
  shows first - of the group asked for, and worth offering?

docs/experiments.md says which paper question each one answers and how
to read it.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Sequence

from src.config.settings import settings
from src.config.thresholds import PipelineThresholds
from src.config.topics import GROUP_OF, TOPIC_GROUPS, TOPICS
from src.evaluation.stats import bootstrap_mean, mean, percentile, rounded

logger = logging.getLogger(__name__)

EXPERIMENTS = Path("data/evaluation/experiments")

# Shared by admission and topics: one /enrich per article, ever.
ENRICH_CACHE = EXPERIMENTS / "enrich_cache.jsonl"

MANUAL = Path("data/evaluation/manual")

SEED = 20261005
RESAMPLES = 2000

TOPIC_KEY = {topic.name: key for key, topic in TOPICS.items()}


# ----------------------------------------------------------------------
# Small shared pieces
# ----------------------------------------------------------------------


def _now() -> str:

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write(name: str, result: dict, report: str, root: Path = EXPERIMENTS) -> Path:

    folder = root / name / _now()
    folder.mkdir(parents=True, exist_ok=True)

    (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "report.md").write_text(report, encoding="utf-8")

    return folder


def table(header: Sequence[str], rows: Iterable[Sequence]) -> str:

    def cell(value) -> str:
        if value is None:
            return "–"
        if isinstance(value, float):
            return f"{value:.3f}"
        return str(value)

    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(cell(value) for value in row) + " |" for row in rows]

    return "\n".join(lines)


def auc(positives: Sequence[float], negatives: Sequence[float]) -> float | None:
    """
    The probability that a random positive scores above a random
    negative, ties counting half (the Mann-Whitney U, scaled). 0.5 is a
    coin; None when either side is empty.
    """

    if not positives or not negatives:
        return None

    wins = 0.0

    for p in positives:
        for n in negatives:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0

    return wins / (len(positives) * len(negatives))


def interval(values: Sequence[float]) -> dict:

    bounds = bootstrap_mean(list(values), seed=SEED, resamples=RESAMPLES)

    return {"mean": rounded(mean(list(values))), "low": rounded(bounds["low"]), "high": rounded(bounds["high"]), "n": len(values)}


# ----------------------------------------------------------------------
# discovery
# ----------------------------------------------------------------------


class _NoLake:
    """Nothing counts as already stored: the yield of a setting, not of today's lake."""

    def list(self, layer, limit=None):
        return []


def discovery_experiment(settings_to_try: list[list[str] | None], per_source: int, sources=None) -> dict:
    """
    For each topic-group setting (None is the baseline: every source,
    every topic), what discovery reads and finds. Fresh request counters
    per setting, so each one's cost is its own.
    """

    from src.repositories.source_repository import SourceRepository
    from src.services.ingestion_service import IngestionService
    from src.services.scraper.discovery import DiscoveryService
    from src.services.scraper.request_stats import RequestStats
    from src.services.scraper.sightings import Sightings

    sources = sources if sources is not None else SourceRepository().list()

    rows = []

    for groups in settings_to_try:

        stats = RequestStats()
        ingestion = IngestionService(
            sources=sources,
            lake=_NoLake(),
            discovery=DiscoveryService(stats=stats),
            sightings=Sightings(),
        )

        started = time.perf_counter()
        found = ingestion.discover_candidates(groups, per_source=per_source)
        elapsed = time.perf_counter() - started

        totals = stats.snapshot()["totals"]
        languages = Counter(candidate["language"] for candidate in found["candidates"])

        rows.append({
            "groups": groups,
            "label": ", ".join(groups) if groups else "all (baseline)",
            "topics": len(found["topics"]),
            "sources": found["totals"]["sources"],
            "attempts": totals["requests"],
            "failedAttempts": totals["failed"],
            "links": found["totals"]["discovered"],
            "candidates": found["totals"]["candidates"],
            "candidatesByLanguage": dict(languages),
            "sourcesFindingNothing": found["totals"]["failed"],
            "seconds": round(elapsed, 2),
        })

    baseline = next((row for row in rows if row["groups"] is None), None)

    for row in rows:
        for key in ("sources", "attempts", "links"):
            row[f"{key}VsBaseline"] = (
                rounded(row[key] / baseline[key], 3) if baseline and baseline[key] else None
            )

    return {"perSource": per_source, "settings": rows}


def discovery_report(result: dict) -> str:

    rows = [
        (
            row["label"], row["sources"], row["sourcesVsBaseline"], row["attempts"], row["links"],
            row["linksVsBaseline"], row["candidates"],
            " / ".join(f"{k} {v}" for k, v in sorted(row["candidatesByLanguage"].items())) or "–",
            row["sourcesFindingNothing"], row["seconds"],
        )
        for row in result["settings"]
    ]

    return "\n".join([
        f"# Discovery by topic group ({result['perSource']} candidates per source)",
        "",
        "Sources read, discovery attempts (one per strategy tried) and links found per setting,",
        "against the baseline of every source for every topic. Nothing in the lake counts as stored,",
        "so the numbers are the setting's yield, not today's novelty.",
        "",
        table(
            ["Setting", "Sources", "× base", "Attempts", "Links", "× base", "Candidates", "by language", "Found nothing", "Seconds"],
            rows,
        ),
        "",
    ])


# ----------------------------------------------------------------------
# selection
# ----------------------------------------------------------------------


def load_rounds(folder: Path) -> list[dict]:

    rounds = []

    for path in sorted(folder.glob("*.json")):
        try:
            rounds.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            logger.warning("Could not read %s", path)

    return rounds


def _blind(round_: dict) -> bool:
    """The AI scored after the editor had chosen: its proposal cannot have anchored them."""

    ai = round_.get("aiSelection") or {}
    queued = round_.get("queued") or {}

    return bool(ai.get("blind")) or bool(ai.get("startedAt") and queued.get("at") and ai["startedAt"] >= queued["at"])


def selection_experiment(rounds: list[dict]) -> dict:
    """
    Over the rounds where both an AI selection finished and a selection
    was sent to analysis: precision (how many AI picks the editor kept),
    recall (how many of the editor's picks the AI had proposed), Jaccard,
    and the AUC of the AI score between picked and not-picked candidates.
    Blind and assisted rounds are kept apart.
    """

    per_round = []
    pooled = defaultdict(lambda: {"picked": [], "skipped": []})

    for round_ in rounds:

        ai = round_.get("aiSelection") or {}
        queued = round_.get("queued") or {}

        if ai.get("status") != "done" or not queued.get("urls"):
            continue

        final = set(queued["urls"])
        proposed = {pick["url"] for pick in ai.get("picks") or []}
        kept = final & proposed
        mode = "blind" if _blind(round_) else "assisted"

        for item in ai.get("scored") or []:
            if item.get("score") is not None:
                pooled[mode]["picked" if item["url"] in final else "skipped"].append(item["score"])

        per_round.append({
            "id": round_["id"],
            "mode": mode,
            "groups": round_.get("groups"),
            "candidates": len(round_.get("candidates") or []),
            "proposed": len(proposed),
            "final": len(final),
            "kept": len(kept),
            "precision": rounded(len(kept) / len(proposed)) if proposed else None,
            "recall": rounded(len(kept) / len(final)) if final else None,
            "jaccard": rounded(len(kept) / len(final | proposed)) if final | proposed else None,
        })

    summary = {}

    for mode in ("blind", "assisted"):

        rows = [row for row in per_round if row["mode"] == mode]

        summary[mode] = {
            "rounds": len(rows),
            "precision": interval([row["precision"] for row in rows if row["precision"] is not None]),
            "recall": interval([row["recall"] for row in rows if row["recall"] is not None]),
            "jaccard": interval([row["jaccard"] for row in rows if row["jaccard"] is not None]),
            "aucAiScore": rounded(auc(pooled[mode]["picked"], pooled[mode]["skipped"])),
            "scoredPicked": len(pooled[mode]["picked"]),
            "scoredSkipped": len(pooled[mode]["skipped"]),
        }

    return {
        "roundsRead": len(rounds),
        "roundsUsable": len(per_round),
        "summary": summary,
        "rounds": per_round,
    }


def selection_report(result: dict) -> str:

    def ci(value: dict) -> str:
        if value["mean"] is None:
            return "–"
        return f"{value['mean']:.2f} [{value['low']:.2f}, {value['high']:.2f}]"

    summary = [
        (mode, s["rounds"], ci(s["precision"]), ci(s["recall"]), ci(s["jaccard"]), s["aucAiScore"], f"{s['scoredPicked']} / {s['scoredSkipped']}")
        for mode, s in result["summary"].items()
    ]

    rounds = [
        (row["id"], row["mode"], ", ".join(row["groups"] or []), row["candidates"], row["proposed"], row["final"], row["kept"], row["precision"], row["recall"])
        for row in result["rounds"]
    ]

    return "\n".join([
        "# Selection: the editor against the AI",
        "",
        f"{result['roundsUsable']} of {result['roundsRead']} rounds had both an AI selection and a selection sent to analysis.",
        "**Blind**: the AI scored after the editor chose (`blind-ai`); **assisted**: the editor saw the AI's picks first,",
        "which inflates agreement. Means over rounds with 95% bootstrap intervals; AUC pooled over every scored candidate.",
        "",
        table(["Mode", "Rounds", "Precision", "Recall", "Jaccard", "AUC of AI score", "scored picked / skipped"], summary),
        "",
        "## Per round",
        "",
        table(["Round", "Mode", "Topics", "Candidates", "AI proposed", "Sent", "Kept", "Precision", "Recall"], rounds),
        "",
    ])


def blind_ai(round_id: str, folder: Path, min_score: float | None = None) -> dict:
    """The AI selection on a round already sent to analysis, recorded as blind."""

    from src.services.selection.ai_selector import DEFAULT_MIN_SCORE, AISelector
    from src.services.selection.rounds import SelectionRounds

    rounds = SelectionRounds(folder)
    round_ = rounds.get(round_id)

    if round_ is None:
        raise SystemExit(f"No round {round_id} in {folder}")

    if not round_.get("queued"):
        raise SystemExit("That round has not been sent to analysis: choose first, then run the AI blind.")

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    selection = AISelector().select(round_["candidates"], round_["groups"], 20, min_score or DEFAULT_MIN_SCORE)

    round_["aiSelection"] = {
        "status": "done",
        "blind": True,
        "startedAt": started,
        "finishedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "limit": 20,
        "minScore": min_score or DEFAULT_MIN_SCORE,
        **selection.to_dict(),
    }
    rounds.save(round_)

    return round_["aiSelection"]


# ----------------------------------------------------------------------
# /enrich, cached - admission and topics
# ----------------------------------------------------------------------


Enrich = Callable[[str], dict]


def http_enrich(backend: str) -> Enrich:
    """
    POST /enrich on a running backend, with the storage key when this
    process has one. Asked with the classifier's floor at 0, so every
    topic comes back with its confidence: the topic minimum can then be
    replayed below today's floor too, and "no topic" measured against it.
    """

    import requests

    key = settings.STORAGE_API_KEY.get_secret_value() if settings.STORAGE_API_KEY else None
    headers = {"X-API-Key": key} if key else {}

    def enrich(url: str) -> dict:
        response = requests.post(
            f"{backend.rstrip('/')}/enrich",
            json={"url": url, "thresholds": {"topic_classifier_threshold": 0.0}},
            headers=headers,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()

    return enrich


def enriched(urls: Sequence[str], enrich: Enrich, cache: Path = ENRICH_CACHE) -> dict[str, dict]:
    """
    {url: what admission and the classifier need} for every URL, from the
    cache where it is there and from `enrich` where not - one line
    appended per URL, so an interrupted run resumes. A URL that fails is
    recorded with its error and not retried until the line is removed.
    """

    known: dict[str, dict] = {}

    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                known[entry["url"]] = entry
            except (ValueError, KeyError):
                continue

    cache.parent.mkdir(parents=True, exist_ok=True)

    with cache.open("a", encoding="utf-8") as out:

        for number, url in enumerate(urls, start=1):

            if url in known:
                continue

            logger.info("enrich %d/%d %s", number, len(urls), url)

            try:
                data = enrich(url)
                entry = {
                    "url": url,
                    "topics": [{"topic": t.get("topic"), "confidence": t.get("confidence")} for t in data.get("topics") or []],
                    "sentiment": data.get("sentiment"),
                    "quality": data.get("quality"),
                    "language": data.get("language"),
                }
            except Exception as exc:
                entry = {"url": url, "error": str(exc)[:300]}

            known[url] = entry
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            out.flush()

    return {url: known[url] for url in urls if url in known}


def _snake(data: dict) -> dict:

    import re

    return {re.sub(r"(?<!^)(?=[A-Z])", "_", key).lower(): value for key, value in (data or {}).items()}


def impact(entry: dict, thresholds: PipelineThresholds):
    """The pipeline's own PositiveImpactScorer over a cached /enrich answer."""

    from src.models.nlp.quality import Quality
    from src.models.nlp.sentiment_result import SentimentResult
    from src.services.admission.positive_impact import PositiveImpactScorer

    sentiment = _snake(entry["sentiment"])
    sentiment.setdefault("emotional_intensity", 0.0)

    return PositiveImpactScorer().score(
        SentimentResult(**{key: sentiment[key] for key in SentimentResult.__dataclass_fields__}),
        Quality(**{key: value for key, value in _snake(entry["quality"]).items() if key in Quality.model_fields}),
        thresholds,
    )


def topic_ok(entry: dict, minimum: float, floor: float | None = None) -> bool:
    """
    The pipeline's two topic steps together: the classifier keeps topics
    at or above its floor (TOPIC_CLASSIFIER_THRESHOLD), and TopicFilter
    admits on any kept topic above the minimum.
    """

    floor = settings.TOPIC_CLASSIFIER_THRESHOLD if floor is None else floor

    return any(
        (topic.get("confidence") or 0) >= floor and (topic.get("confidence") or 0) > minimum
        for topic in entry.get("topics") or []
    )


# ----------------------------------------------------------------------
# admission
# ----------------------------------------------------------------------


def admission_experiment(
    articles: dict[str, dict],
    labels: dict[str, bool],
    topic_mins: Sequence[float],
    impact_mins: Sequence[float],
) -> dict:
    """
    Every (topic minimum, impact minimum) pair replayed over the same
    enriched articles: how many would be admitted, and - for articles an
    editor chose for or against - precision and recall of "admitted"
    against "chosen".
    """

    usable = {url: entry for url, entry in articles.items() if "error" not in entry}

    grid = []

    for topic_min in topic_mins:
        for impact_min in impact_mins:

            thresholds = PipelineThresholds(topic_min_confidence=topic_min, positive_impact_min_score=impact_min)

            # The floor moves with the minimum here: below today's floor,
            # the question is what a lower floor would let through.
            admitted = {
                url
                for url, entry in usable.items()
                if topic_ok(entry, topic_min, floor=min(topic_min, settings.TOPIC_CLASSIFIER_THRESHOLD))
                and impact(entry, thresholds).passed
            }

            labelled = [url for url in usable if url in labels]
            chosen = {url for url in labelled if labels[url]}
            admitted_labelled = admitted & set(labelled)
            hits = admitted_labelled & chosen

            grid.append({
                "topicMin": topic_min,
                "impactMin": impact_min,
                "admitted": len(admitted),
                "rate": rounded(len(admitted) / len(usable)) if usable else None,
                "precision": rounded(len(hits) / len(admitted_labelled)) if admitted_labelled else None,
                "recall": rounded(len(hits) / len(chosen)) if chosen else None,
            })

    default = PipelineThresholds()
    scores = {url: impact(entry, default).score for url, entry in usable.items()}

    return {
        "articles": len(articles),
        "enriched": len(usable),
        "failed": len(articles) - len(usable),
        "labelled": sum(1 for url in usable if url in labels),
        "chosen": sum(1 for url in usable if labels.get(url)),
        "noTopicAtAll": sum(1 for entry in usable.values() if not topic_ok(entry, 0.0)),
        # Does the impact score separate what the editor chose from what
        # they passed over? 0.5 is a coin.
        "aucImpactScore": rounded(auc(
            [scores[url] for url in usable if labels.get(url) is True],
            [scores[url] for url in usable if labels.get(url) is False],
        )),
        "defaults": {"topicMin": default.topic_min_confidence, "impactMin": default.positive_impact_min_score},
        "grid": grid,
    }


def admission_report(result: dict) -> str:

    rows = [
        (row["topicMin"], row["impactMin"], row["admitted"], row["rate"], row["precision"], row["recall"])
        for row in result["grid"]
    ]

    return "\n".join([
        "# Admission thresholds, replayed",
        "",
        f"{result['enriched']} articles enriched ({result['failed']} failed); {result['labelled']} labelled by an editor's choice,"
        f" {result['chosen']} of them chosen. {result['noTopicAtAll']} had no topic at today's classifier floor"
        f" ({settings.TOPIC_CLASSIFIER_THRESHOLD}), so today's topic filter rejects them whatever its minimum.",
        f"Defaults: topic minimum {result['defaults']['topicMin']}, impact minimum {result['defaults']['impactMin']}.",
        f"AUC of the positive-impact score, chosen against passed over: {result['aucImpactScore'] if result['aucImpactScore'] is not None else '–'} (0.5 is a coin).",
        "Duplicate detection is not replayed.",
        "",
        table(["Topic min", "Impact min", "Admitted", "Rate", "Precision vs editor", "Recall vs editor"], rows),
        "",
    ])


def round_labels(rounds: list[dict]) -> dict[str, bool]:
    """Every candidate of a round sent to analysis: True if the editor sent it, False if not."""

    labels = {}

    for round_ in rounds:

        sent = set((round_.get("queued") or {}).get("urls") or [])

        if not sent:
            continue

        for candidate in round_.get("candidates") or []:
            labels[candidate["url"]] = candidate["url"] in sent

    return labels


# ----------------------------------------------------------------------
# topics
# ----------------------------------------------------------------------


def labelled_articles(folder: Path = MANUAL) -> dict[str, str]:
    """{article URL: the topic its facts were most often labelled with}."""

    by_article: dict[str, Counter] = defaultdict(Counter)

    for path in sorted(folder.glob("fact*.json")):
        try:
            fact = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if fact.get("articleUrl") and fact.get("topic") in TOPICS:
            by_article[fact["articleUrl"]][fact["topic"]] += 1

    return {url: counts.most_common(1)[0][0] for url, counts in by_article.items()}


def topics_experiment(articles: dict[str, dict], gold: dict[str, str]) -> dict:

    rows = []

    for url, topic in gold.items():

        entry = articles.get(url)

        if entry is None or "error" in entry:
            continue

        ranked = sorted(entry.get("topics") or [], key=lambda t: t.get("confidence") or 0, reverse=True)
        predicted = [TOPIC_KEY.get(t.get("topic"), t.get("topic")) for t in ranked]

        rows.append({
            "url": url,
            "gold": topic,
            "goldGroup": GROUP_OF[topic],
            "top": predicted[0] if predicted else None,
            "topGroup": GROUP_OF.get(predicted[0]) if predicted else None,
            "inTop3": topic in predicted[:3],
            "topConfidence": rounded(ranked[0].get("confidence")) if ranked else None,
            # What the pipeline itself sees: nothing at today's floor
            # means the article is rejected as off-topic.
            "noTopicAtFloor": not topic_ok(entry, 0.0),
        })

    n = len(rows)

    def share(test) -> dict:
        return interval([1.0 if test(row) else 0.0 for row in rows])

    confusion = {group: Counter() for group in TOPIC_GROUPS}

    for row in rows:
        confusion[row["goldGroup"]][row["topGroup"] or "no topic"] += 1

    return {
        "articles": n,
        "top1": share(lambda row: row["top"] == row["gold"]),
        "top3": share(lambda row: row["inTop3"]),
        "group": share(lambda row: row["topGroup"] == row["goldGroup"]),
        "noTopic": share(lambda row: row["noTopicAtFloor"]),
        "confusion": {group: dict(counts) for group, counts in confusion.items()},
        "rows": rows,
    }


def topics_report(result: dict) -> str:

    def ci(value: dict) -> str:
        if value["mean"] is None:
            return "–"
        return f"{value['mean']:.2f} [{value['low']:.2f}, {value['high']:.2f}]"

    columns = list(TOPIC_GROUPS) + ["no topic"]

    return "\n".join([
        "# The topic classifier against the annotator",
        "",
        f"{result['articles']} labelled articles. Shares with 95% bootstrap intervals.",
        "",
        table(
            ["Top-1 topic", "Gold in top 3", "Top-1 group", f"No topic at the floor ({settings.TOPIC_CLASSIFIER_THRESHOLD})"],
            [(ci(result["top1"]), ci(result["top3"]), ci(result["group"]), ci(result["noTopic"]))],
        ),
        "",
        "## Group confusion (rows: annotator, columns: classifier's top topic)",
        "",
        table(["Annotator \\ classifier"] + columns, [
            [group] + [result["confusion"][group].get(column, 0) for column in columns]
            for group in TOPIC_GROUPS
        ]),
        "",
    ])


# ----------------------------------------------------------------------
# emphasis
# ----------------------------------------------------------------------

# The five live one-group rounds of 2026-10-09, run six times, every
# candidate's reading and source parts recorded (runs.json), and the hand
# labels of what they showed (labelled.json).
ALIGNMENT = EXPERIMENTS / "alignment" / "20261009T120000Z"

# The candidates those labels left out - all 60 from rounds' reserves,
# which more weight on the topic brings into view. Labelled 2026-10-13 the
# same way, blind to any score.
RESERVE_LABELS = EXPERIMENTS / "emphasis" / "reserve-labels.json"

# The runs that recorded a group fit (the first, "before", predates it),
# and the last two: the ten rounds the 2026-10-09 topic weight was chosen
# on. The last two read the same feeds an hour apart (94 of 100 shown the
# same), so they are closer to five rounds than ten.
FIT_RUNS = ("iter1", "iter2", "iter3", "iter4", "recheck")
LAST_RUNS = ("iter4", "recheck")

# The weights from 2026-10-09 until the emphasis: the row to beat.
BEFORE = {"news": 0.51, "topic": 0.15, "record": 0.21, "reliability": 0.13}

EMPHASES = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8, 0.9, 1.0)

# Where the topic part could saturate instead of TOPIC_RANGE's 0.10: a
# story of two groups (gene therapy, science and health) fits less than
# one squarely technical, so stopping earlier counts belonging rather than
# squareness. Tried at a few emphases.
TOPIC_HIGHS = (0.10, 0.06, 0.04, 0.03, 0.02)
TOPIC_HIGH_EMPHASES = (0.5, 0.6, 0.7)


def load_alignment(folder: Path = ALIGNMENT, extra: Sequence[Path] = (RESERVE_LABELS,)) -> tuple[list[dict], dict[str, dict], dict]:
    """The rounds of the runs that recorded a group fit, each with its run's name; the labels by url; how many came from where."""

    runs = json.loads((folder / "runs.json").read_text(encoding="utf-8"))["runs"]

    labels = {c["url"]: c for c in json.loads((folder / "labelled.json").read_text(encoding="utf-8"))["candidates"]}
    provenance = {(folder / "labelled.json").as_posix(): len(labels)}

    for path in extra:
        added = json.loads(Path(path).read_text(encoding="utf-8"))["candidates"]
        labels.update({c["url"]: c for c in added})
        provenance[Path(path).as_posix()] = len(added)

    rounds = [
        {**round_, "run": run["run"]}
        for run in runs
        if run["run"] in FIT_RUNS
        for round_ in run["rounds"]
    ]

    return rounds, labels, provenance


def _recorded_reading(reading: dict | None):
    """A Reading from what a round recorded: its similarities, not its vector or its topics."""

    from src.services.selection.mission_screen import Reading

    if not reading:
        return None

    return Reading(
        nearest_topic=reading["nearestTopic"], topic=reading["topic"],
        nearest_off=reading["nearestOff"], off=reading["off"], impact=reading["impact"],
    )


def reordered(round_: dict, weighted: dict, topic_bounds: tuple[float, float] | None = None) -> list[dict]:
    """
    A recorded round's candidates, shown and in reserve, in the order the
    ranking gives them under `weighted`: each re-scored with ranking.score
    from its recorded reading and source parts, then ranking.ordered -
    the round's own code, not a copy. one_per_story compares embeddings,
    which rounds do not record; each of the round's stories (`sameStoryAs`
    as recorded) gets a vector of its own instead, so the round's grouping
    holds and only which version leads can change.
    """

    import numpy as np

    from src.services.selection import ranking

    found = round_["candidates"] + round_["reserve"]

    story_of = {c["url"]: c.get("sameStoryAs") or c["url"] for c in found}
    stories = {story: index for index, story in enumerate(dict.fromkeys(story_of.values()))}
    basis = np.eye(len(stories))

    fresh, fits, nearest, vectors = [], {}, {}, {}

    for candidate in found:

        url = candidate["url"]
        reading = candidate.get("reading")
        fit = (reading or {}).get("groupFit")

        news = ranking.news_part(_recorded_reading(reading))
        topic = ranking.topic_part(fit, topic_bounds or ranking.TOPIC_RANGE)
        score = ranking.score(news, topic, candidate["rank"]["record"], candidate["rank"]["reliability"], weighted)

        # Rounded as a round rounds it, so ties fall as they would.
        fresh.append({"url": url, "rank": {"score": round(score, 3)}})

        if fit is not None:
            fits[url] = fit
            nearest[url] = reading["nearestTopic"]

        vectors[url] = basis[stories[story_of[url]]]

    return ranking.ordered(fresh, fits, nearest, vectors)


def _slot(label: dict | None, group: str) -> Counter:
    """What one place in a list holds, as counts."""

    if label is None:
        return Counter(shown=1, unlabelled=1)

    of_group = group in label["belongsTo"]
    article = label["kind"] == "article"
    worth = label["hand"] >= 1
    positive = label["hand"] == 2

    return Counter(
        shown=1,
        ofGroup=int(of_group),
        anotherGroup=int(article and not of_group),
        notArticle=int(not article),
        worthOffering=int(worth),
        clearlyPositive=int(positive),
        worthOfferingOfGroup=int(worth and of_group),
        clearlyPositiveOfGroup=int(positive and of_group),
        notWorthOffering=int(not worth),
    )


def _rank_auc(items: Sequence[tuple[float, bool]]) -> float | None:
    """`auc` by ranks (ties averaged, so they count half): the same number, fast enough to bootstrap."""

    positives = sum(1 for _, positive in items if positive)
    negatives = len(items) - positives

    if not positives or not negatives:
        return None

    ordered = sorted(items, key=lambda item: item[0])
    rank_sum = 0.0
    i = 0

    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1][0] == ordered[i][0]:
            j += 1
        average = (i + j) / 2 + 1
        rank_sum += average * sum(1 for k in range(i, j + 1) if ordered[k][1])
        i = j + 1

    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def auc_interval(items: Sequence[tuple[float, bool]]) -> dict:
    """The AUC of (score, is positive) pairs with a 95% bootstrap interval over the pairs."""

    point = _rank_auc(items)

    if point is None:
        return {"auc": None, "low": None, "high": None, "n": len(items)}

    rng = random.Random(SEED)
    n = len(items)
    resampled = []

    for _ in range(RESAMPLES):
        value = _rank_auc([items[rng.randrange(n)] for _ in range(n)])
        if value is not None:
            resampled.append(value)

    return {
        "auc": rounded(point, 3),
        "low": rounded(percentile(resampled, 2.5), 3),
        "high": rounded(percentile(resampled, 97.5), 3),
        "n": n,
        "positives": sum(1 for _, positive in items if positive),
    }


def emphasis_setting(rounds: list[dict], labels: dict[str, dict], weighted: dict, topic_bounds=None, aucs: bool = True) -> dict:
    """
    Under one set of weights: what the first twenty and the first ten of
    `rounds` hold, and - over every labelled article of those rounds, one
    per round group, its latest reading - how well the score separates
    the group's stories from another's and those worth offering from not.
    """

    from src.services.selection import ranking

    twenty, ten = Counter(), Counter()

    for round_ in rounds:

        group = round_["groups"][0]

        for place, candidate in enumerate(reordered(round_, weighted, topic_bounds)[:20]):
            slot = _slot(labels.get(candidate["url"]), group)
            twenty.update(slot)
            if place < 10:
                ten.update(slot)

    setting = {"firstTwenty": dict(twenty), "firstTen": dict(ten)}

    if not aucs:
        return setting

    latest: dict[tuple[str, str], dict] = {}

    for round_ in rounds:
        for candidate in round_["candidates"] + round_["reserve"]:
            latest[(round_["groups"][0], candidate["url"])] = candidate

    of_group, worth, worth_in_group = [], [], []

    for (group, url), candidate in latest.items():

        label = labels.get(url)

        if label is None or label["kind"] != "article":
            continue

        reading = candidate.get("reading")
        score = ranking.score(
            ranking.news_part(_recorded_reading(reading)),
            ranking.topic_part((reading or {}).get("groupFit"), topic_bounds or ranking.TOPIC_RANGE),
            candidate["rank"]["record"], candidate["rank"]["reliability"], weighted,
        )

        belongs = group in label["belongsTo"]
        of_group.append((score, belongs))
        worth.append((score, label["hand"] >= 1))

        if belongs:
            worth_in_group.append((score, label["hand"] >= 1))

    setting["auc"] = {
        "ofGroup": auc_interval(of_group),
        "worthOffering": auc_interval(worth),
        "worthOfferingInGroup": auc_interval(worth_in_group),
    }

    return setting


def emphasis_experiment(rounds: list[dict], labels: dict[str, dict], emphases: Sequence[float] = EMPHASES, provenance: dict | None = None) -> dict:

    from src.services.selection import ranking

    chosen = ranking.DEFAULT_TOPIC_EMPHASIS
    emphases = sorted(set(emphases) | {chosen, ranking.WITHOUT_TOPIC})

    sets = {
        "last": [round_ for round_ in rounds if round_["run"] in LAST_RUNS],
        "all": rounds,
    }

    def rows(chosen_rounds: list[dict]) -> list[dict]:
        out = [{"setting": "before", "emphasis": None, "weights": BEFORE, **emphasis_setting(chosen_rounds, labels, BEFORE)}]
        for emphasis in emphases:
            weighted = ranking.weights(emphasis)
            out.append({
                "setting": "chosen" if emphasis == chosen else "emphasis",
                "emphasis": emphasis,
                "weights": {part: round(weight, 4) for part, weight in weighted.items()},
                **emphasis_setting(chosen_rounds, labels, weighted),
            })
        return out

    # The topic part saturating earlier than TOPIC_RANGE: first places only.
    tried = [
        {
            "topicRange": [ranking.TOPIC_RANGE[0], high],
            "emphasis": emphasis,
            **{
                name: emphasis_setting(chosen_rounds, labels, ranking.weights(emphasis), (ranking.TOPIC_RANGE[0], high), aucs=False)
                for name, chosen_rounds in sets.items()
            },
        }
        for high in TOPIC_HIGHS
        for emphasis in TOPIC_HIGH_EMPHASES
    ]

    # What the chosen default changes, round by round, and in the last
    # run's lists: which stories leave the first twenty and which come in.
    per_round, moved = [], []

    for round_ in sets["last"]:

        group = round_["groups"][0]
        before = reordered(round_, BEFORE)[:20]
        after = reordered(round_, ranking.weights(chosen))[:20]

        def count(listed: list[dict]) -> Counter:
            return sum((_slot(labels.get(c["url"]), group) for c in listed), Counter())

        per_round.append({"run": round_["run"], "round": round_["round"], "group": group, "before": dict(count(before)), "chosen": dict(count(after))})

        if round_["run"] != LAST_RUNS[-1]:
            continue

        titles = {c["url"]: c.get("title") for c in round_["candidates"] + round_["reserve"]}
        urls_before, urls_after = {c["url"] for c in before}, {c["url"] for c in after}

        for direction, urls, other in (("out", [c["url"] for c in before], urls_after), ("in", [c["url"] for c in after], urls_before)):
            for url in urls:
                if url in other:
                    continue
                label = labels.get(url) or {}
                moved.append({
                    "group": group, "direction": direction, "url": url, "title": titles.get(url),
                    "hand": label.get("hand"), "belongsTo": label.get("belongsTo"), "kind": label.get("kind"),
                })

    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        # Where the labels came from - the first is the rounds' own folder.
        "labels": provenance or {},
        "rounds": {name: len(chosen_rounds) for name, chosen_rounds in sets.items()},
        "runs": {"last": list(LAST_RUNS), "all": list(FIT_RUNS)},
        "chosen": chosen,
        "before": BEFORE,
        "seed": SEED,
        "resamples": RESAMPLES,
        "settings": {name: rows(chosen_rounds) for name, chosen_rounds in sets.items()},
        "topicRangeTried": tried,
        "perRound": per_round,
        "moved": moved,
    }


def emphasis_report(result: dict) -> str:

    def name(row: dict) -> str:
        if row["setting"] == "before":
            return "before (0.51 / 0.15 / 0.21 / 0.13)"
        label = f"{row['emphasis']:.2f}"
        return f"**{label} (chosen)**" if row["setting"] == "chosen" else label

    def ci(value: dict) -> str:
        return "–" if value["auc"] is None else f"{value['auc']:.3f} [{value['low']:.3f}, {value['high']:.3f}]"

    def places(rows: list[dict]) -> str:
        return table(
            ["Emphasis", "News / topic", "Of the group", "Of another group", "Not an article", "Worth offering or clearly positive",
             "Clearly positive", "Worth offering, of the group", "Clearly positive, of the group", "Not worth offering",
             "First ten: of the group", "First ten: worth offering, of the group"],
            [
                (
                    name(row), f"{row['weights']['news']:.2f} / {row['weights']['topic']:.2f}",
                    *(row["firstTwenty"].get(key, 0) for key in (
                        "ofGroup", "anotherGroup", "notArticle", "worthOffering", "clearlyPositive",
                        "worthOfferingOfGroup", "clearlyPositiveOfGroup", "notWorthOffering",
                    )),
                    row["firstTen"].get("ofGroup", 0), row["firstTen"].get("worthOfferingOfGroup", 0),
                )
                for row in rows
            ],
        )

    def separation(rows: list[dict]) -> str:
        return table(
            ["Emphasis", "Of the group vs another", "Worth offering vs not", "Worth offering vs not, within the group"],
            [(name(row), ci(row["auc"]["ofGroup"]), ci(row["auc"]["worthOffering"]), ci(row["auc"]["worthOfferingInGroup"])) for row in rows],
        )

    last, every = result["settings"]["last"], result["settings"]["all"]
    shown = {name: rows[0]["firstTwenty"]["shown"] for name, rows in result["settings"].items()}
    unlabelled = max(row["firstTwenty"].get("unlabelled", 0) for rows in result["settings"].values() for row in rows)

    def at(rows: list[dict], setting: str, emphasis: float | None = None) -> dict:
        """A row by its setting ("before", "chosen"), or by its emphasis whatever it is labelled."""
        if emphasis is not None:
            return next(row for row in rows if row["emphasis"] == emphasis)
        return next(row for row in rows if row["setting"] == setting)

    def numbers(row: dict) -> str:
        twenty, ten = row["firstTwenty"], row["firstTen"]
        return (
            f"{twenty.get('ofGroup', 0)} of the group, {twenty.get('worthOfferingOfGroup', 0)} worth offering of it, "
            f"{twenty.get('clearlyPositiveOfGroup', 0)} clearly positive of it, first ten {ten.get('ofGroup', 0)} of the group"
        )

    chosen_last, chosen_all = at(last, "chosen"), at(every, "chosen")
    higher = [row for row in last if row["emphasis"] is not None and row["emphasis"] > result["chosen"]]
    beyond = (
        f" One step higher ({higher[0]['emphasis']:.2f}): {numbers(higher[0])}."
        if higher else ""
    )

    chosen = [
        f"## Chosen: {result['chosen']}",
        "",
        f"Ten rounds, first twenty: before, {numbers(at(last, 'before'))}; at 0, {numbers(at(last, 'emphasis', 0.0))};",
        f"at {result['chosen']}, {numbers(chosen_last)}.{beyond} Over all 25 rounds at {result['chosen']}: {numbers(chosen_all)}",
        f"(before: {numbers(at(every, 'before'))}).",
    ]

    tried = table(
        ["Topic part full at", "Emphasis", "Of the group (10)", "Worth offering, of the group (10)", "Clearly positive, of the group (10)",
         "First ten: of the group (10)", "Of the group (25)", "Worth offering, of the group (25)", "Clearly positive, of the group (25)"],
        [
            (
                f"{row['topicRange'][1]:.2f}", f"{row['emphasis']:.1f}",
                row["last"]["firstTwenty"].get("ofGroup", 0), row["last"]["firstTwenty"].get("worthOfferingOfGroup", 0),
                row["last"]["firstTwenty"].get("clearlyPositiveOfGroup", 0), row["last"]["firstTen"].get("ofGroup", 0),
                row["all"]["firstTwenty"].get("ofGroup", 0), row["all"]["firstTwenty"].get("worthOfferingOfGroup", 0),
                row["all"]["firstTwenty"].get("clearlyPositiveOfGroup", 0),
            )
            for row in result["topicRangeTried"]
        ],
    )

    by_round = table(
        ["Run", "Group", "Of the group", "Worth offering, of the group", "Clearly positive, of the group", "Not worth offering"],
        [
            (
                row["run"], row["group"],
                *(f"{row['before'].get(key, 0)} -> {row['chosen'].get(key, 0)}" for key in (
                    "ofGroup", "worthOfferingOfGroup", "clearlyPositiveOfGroup", "notWorthOffering",
                )),
            )
            for row in result["perRound"]
        ],
    )

    scale = {2: "clearly positive", 1: "worth offering", 0: "not worth offering", None: "unlabelled"}

    moved = []
    for group in dict.fromkeys(row["group"] for row in result["moved"]):
        moved.append(f"- **{group}**")
        for row in result["moved"]:
            if row["group"] == group:
                belongs = ", ".join(row["belongsTo"] or []) or "no group"
                moved.append(f"  - {row['direction']}: {row['title']} ({scale[row['hand']]}; {belongs})")

    return "\n".join([
        "# Topic emphasis: how much the topic weighs against positive impact",
        "",
        f"{result['date']}. Every candidate of the 2026-10-09 alignment rounds that recorded a group fit, shown or in",
        f"reserve, re-scored at each emphasis with `src/services/selection/ranking.py`'s own `score` and `ordered`, from",
        "the readings and source parts the rounds recorded: nothing embedded or fetched again. The emphasis splits the",
        "story's 0.6 of the score between positive impact (news) and the fit with the group asked for (topic); the",
        "source's record and reliability keep 0.25 and 0.15. Emphasis 0 is the 2026-10-06 score; *before* is the",
        "weights from 2026-10-09 until this change. Stories are grouped as each round grouped them (`sameStoryAs`).",
        "",
        "Labels (hand: clearly positive / worth offering / not worth offering; the groups each story belongs to; whether",
        "it is an article): " + "; ".join(f"{count} from `{path}`" for path, count in result["labels"].items()) + ".",
        f"Unlabelled in any first twenty: {unlabelled}. Labels are Claude's, not yet checked by a person.",
        "",
        *chosen,
        "",
        f"## The first twenty, ten rounds ({shown['last']} places)",
        "",
        "The five one-group rounds of the last two runs (iter4 and the recheck an hour later, 94 of 100 shown the same):",
        "the set the 2026-10-09 topic weight was chosen on.",
        "",
        places(last),
        "",
        f"## The first twenty, 25 rounds ({shown['all']} places)",
        "",
        "Every run that recorded a group fit (iter1 to the recheck): the same five feeds read five times in a day, so not",
        "25 independent rounds either.",
        "",
        places(every),
        "",
        "## How well the score separates (ten rounds)",
        "",
        "AUC over each round group's labelled articles, shown or in reserve (latest reading), with a 95% bootstrap",
        f"interval ({result['resamples']} resamples, seed {result['seed']}). Before the partition and the one-story rule.",
        "",
        separation(last),
        "",
        "## The topic part saturating earlier (tried, not adopted)",
        "",
        "`TOPIC_RANGE` gives a story full topic marks at a fit of 0.10. A story of two groups fits less than one squarely",
        "technical; full marks earlier would count belonging rather than squareness.",
        "",
        tried,
        "",
        f"## The chosen {result['chosen']} against before, round by round",
        "",
        by_round,
        "",
        "## What left and entered the first twenty (the recheck run)",
        "",
        *moved,
        "",
    ])


# ----------------------------------------------------------------------
# The command
# ----------------------------------------------------------------------


def _floats(text: str) -> list[float]:

    return [float(value) for value in text.split(",") if value.strip()]


def parser() -> argparse.ArgumentParser:

    root = argparse.ArgumentParser(
        prog="python -m src.evaluation.experiments",
        description="Experiments on discovery, selection, admission and topics.",
    )
    commands = root.add_subparsers(dest="command", required=True)

    discovery = commands.add_parser("discovery", help="what each topic-group setting reads and finds")
    discovery.add_argument(
        "--group", action="append",
        help="a setting: one group or several, comma-separated; repeat per setting (default: each group alone)",
    )
    discovery.add_argument("--per-source", type=int, default=3)
    discovery.add_argument("--no-baseline", action="store_true", help="skip the every-source, every-topic baseline")

    commands.add_parser("selection", help="the editor's picks against the AI's, from the recorded rounds")

    blind = commands.add_parser("blind-ai", help="run the AI selection on a round already sent to analysis")
    blind.add_argument("--round", required=True)
    blind.add_argument("--min-score", type=float)

    admission = commands.add_parser("admission", help="admission thresholds replayed over enriched articles")
    admission.add_argument("--backend", default="http://127.0.0.1:8000")
    admission.add_argument("--articles", choices=("rounds", "facts"), default="rounds")
    admission.add_argument("--topic-min", default="0.30,0.35,0.40,0.45")
    admission.add_argument("--impact-min", default="0.10,0.20,0.25,0.30")

    topics = commands.add_parser("topics", help="the topic classifier against the labelled facts")
    topics.add_argument("--backend", default="http://127.0.0.1:8000")

    emphasis = commands.add_parser("emphasis", help="the ranking re-scored at several topic emphases over labelled rounds")
    emphasis.add_argument("--alignment", default=str(ALIGNMENT), help="a folder with runs.json and labelled.json")
    emphasis.add_argument(
        "--labels", action="append",
        help=f"more labels (repeatable; default {RESERVE_LABELS})",
    )
    emphasis.add_argument("--emphasis", help="comma-separated emphases (default %s)" % ",".join(str(e) for e in EMPHASES))

    return root


def main(argv: list[str] | None = None) -> int:

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    args = parser().parse_args(argv)
    rounds_folder = settings.LAKE_PATH / "stats" / "selection"

    if args.command == "discovery":
        to_try = [[g.strip() for g in setting.split(",") if g.strip()] for setting in (args.group or [])] or [[g] for g in TOPIC_GROUPS]
        unknown = sorted({g for setting in to_try for g in setting} - set(TOPIC_GROUPS))
        if unknown:
            raise SystemExit(f"Unknown group(s): {', '.join(unknown)}")
        if not args.no_baseline:
            to_try = [None] + to_try
        result = discovery_experiment(to_try, args.per_source)
        name, report = "discovery", discovery_report(result)

    elif args.command == "selection":
        result = selection_experiment(load_rounds(rounds_folder))
        name, report = "selection", selection_report(result)

    elif args.command == "blind-ai":
        state = blind_ai(args.round, rounds_folder, args.min_score)
        print(json.dumps({k: state[k] for k in ("status", "model", "calls", "elapsedMs")}, indent=1))
        print(f"{len(state['picks'])} picks recorded on round {args.round} as blind; run `selection` to compare.")
        return 0

    elif args.command == "admission":
        if args.articles == "facts":
            urls, labels = list(labelled_articles()), {}
        else:
            rounds = load_rounds(rounds_folder)
            urls = list(dict.fromkeys(c["url"] for r in rounds for c in r.get("candidates") or []))
            labels = round_labels(rounds)
        articles = enriched(urls, http_enrich(args.backend))
        result = admission_experiment(articles, labels, _floats(args.topic_min), _floats(args.impact_min))
        name, report = "admission", admission_report(result)

    elif args.command == "emphasis":
        rounds, labels, provenance = load_alignment(Path(args.alignment), [Path(path) for path in args.labels or [RESERVE_LABELS]])
        emphases = _floats(args.emphasis) if args.emphasis else EMPHASES
        result = emphasis_experiment(rounds, labels, emphases, provenance)
        name, report = "emphasis", emphasis_report(result)

    else:
        gold = labelled_articles()
        articles = enriched(list(gold), http_enrich(args.backend))
        result = topics_experiment(articles, gold)
        name, report = "topics", topics_report(result)

    folder = write(name, result, report)
    print(report)
    print(f"Written to {folder}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
