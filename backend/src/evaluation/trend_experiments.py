"""
The trending lens's experiments (docs/decisions/trends.md), run through
`python -m src.evaluation.experiments`:

    cd backend
    uv run python -m src.evaluation.experiments topics24
    uv run python -m src.evaluation.experiments trends run      # a day's rounds, to label
    uv run python -m src.evaluation.experiments trends report   # the labelled days

- **topics24** (T3) re-screens every labelled candidate recorded with a
  title under the 23 topics of the morning of 2026-10-26 and under the 24
  with `internet_culture`, and applies the rule written before it ran
  (data/evaluation/experiments/topics24/rule.md). Needs inference/.
- **trends** (T6), below.

Apart from experiments.py because they belong to one feature, and that
file was 1,566 lines; they write where every experiment writes
(`experiments.write`).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


from src.config.topics import TOPIC_GROUPS, TOPICS
from src.models.nlp.topics import Topic
from src.services.scraper.article_stats import comparable_url
from src.services.selection import ranking
from src.services.selection.mission_screen import Candidate, MissionScreen

EXPERIMENTS = Path("data/evaluation/experiments")

RANKING = EXPERIMENTS / "ranking" / "20261006T133348Z" / "result.json"
ALIGNMENT = EXPERIMENTS / "alignment" / "20261009T120000Z" / "labelled.json"
RESERVE = EXPERIMENTS / "emphasis" / "reserve-labels.json"

NEW_TOPIC = "internet_culture"

# The 24th topic as it was proposed and measured on 2026-10-26, and
# Entertainment without the three viral keywords it would have given up.
# Not adopted (the rule's fit and pull checks failed: docs/decisions/
# trends.md, "internet_culture, measured"), so it lives here rather than in
# src/config/topics.py, and the measurement can be run again as it was.
INTERNET_CULTURE = Topic(
    name="Internet Culture & Trends",
    description="Viral trends, memes, social media challenges, online communities and internet culture: what people share online, why it spreads and what it does offline.",
    keywords=[
        "viral trend", "internet culture", "social media trend",
        "meme", "TikTok", "viral video", "hashtag", "online community",
    ],
)

ENTERTAINMENT_AFTER = Topic(
    name="Entertainment",
    description="Cinema, television, music, festivals, animation and cultural productions.",
    keywords=[
        "movie", "film", "music", "concert", "festival",
        "animation", "cartoon", "pop culture", "comic",
    ],
)

# The rule's bounds (topics24/rule.md), written before the run.
MAX_LEAK = 2
MAX_LOSS = 2
MAX_FIT_DROP = 0.02
MAX_PULL = 3


def topics_before() -> dict[str, Topic]:
    """The 23 configured topics (Entertainment still holding the viral keywords)."""

    return dict(TOPICS)


def topics_after() -> dict[str, Topic]:
    """The 24 proposed on 2026-10-26: the keywords moved, internet_culture added after Culture's own."""

    after = {key: (ENTERTAINMENT_AFTER if key == "entertainment" else topic) for key, topic in TOPICS.items()}
    position = list(after).index("inspiration") + 1
    items = list(after.items())

    return dict(items[:position] + [(NEW_TOPIC, INTERNET_CULTURE)] + items[position:])


def load_labelled(
    ranking_file: Path = RANKING,
    alignment_file: Path = ALIGNMENT,
    reserve_file: Path = RESERVE,
    positive_sources: set[str] | None = None,
) -> list[dict]:
    """
    Every labelled candidate recorded with a title, once each by host and
    path: {url, title, summary, language, hand, belongsTo, exempt, set}.
    `positive_sources`, the source ids marked positive_editorial, decide
    exemption where a file does not record it.
    """

    positive_sources = positive_sources or set()
    seen: set[str] = set()
    out: list[dict] = []

    def add(item: dict, origin: str, exempt: bool, language: str | None) -> None:

        key = comparable_url(item["url"])

        if key in seen or not item.get("title") or item.get("hand") is None:
            return

        seen.add(key)
        out.append({
            "url": item["url"],
            "title": item["title"],
            "summary": item.get("summary"),
            "language": language,
            "hand": int(item["hand"]),
            "belongsTo": item.get("belongsTo"),
            "exempt": exempt,
            "set": origin,
        })

    for item in json.loads(Path(ranking_file).read_text(encoding="utf-8"))["candidates"]:
        add(item, "2026-10-06", bool(item.get("positive_editorial")), item.get("lang"))

    for path, origin in ((alignment_file, "2026-10-09"), (reserve_file, "2026-10-13")):
        for item in json.loads(Path(path).read_text(encoding="utf-8"))["candidates"]:
            add(item, origin, item.get("source") in positive_sources, None)

    return out


def _assess(screen: MissionScreen, candidates: list[dict]):

    return screen.assess(
        [Candidate(title=c["title"], summary=c["summary"], language=c["language"]) for c in candidates],
        exempt=[c["exempt"] for c in candidates],
    )


def _fit(reading, group: str, topics: dict) -> float | None:
    """The fit for a round of `group`, over the topics this screen compared with; internet_culture is Culture's."""

    return ranking.group_fit(
        reading, [t for t in topics if t in TOPIC_GROUPS[group] or (group == "culture" and t == NEW_TOPIC)],
    )


def topics24_experiment(candidates: list[dict], before: MissionScreen, after: MissionScreen) -> dict:
    """The four quantities of the rule, and what decided each."""

    first, second = _assess(before, candidates), _assess(after, candidates)

    leaked, lost, pulled, nearest_new, changed_nearest = [], [], [], [], 0
    fits_before: list[tuple[float, bool]] = []
    fits_after: list[tuple[float, bool]] = []

    def brief(c: dict, **extra) -> dict:
        return {"url": c["url"], "title": c["title"], "hand": c["hand"], "set": c["set"], **extra}

    for c, a, b in zip(candidates, first, second):

        out_before, out_after = a.verdict is not None, b.verdict is not None

        if out_before and not out_after and c["hand"] == 0:
            leaked.append(brief(c, leftOutAs=a.verdict.off_mission, margin=a.verdict.margin))

        if not out_before and out_after and c["hand"] >= 1:
            lost.append(brief(c, leftOutAs=b.verdict.off_mission, margin=b.verdict.margin))

        if a.reading and b.reading:

            if a.reading.nearest_topic != b.reading.nearest_topic:
                changed_nearest += 1

            if b.reading.nearest_topic == NEW_TOPIC:
                nearest_new.append(brief(c, leftOut=b.verdict.off_mission if out_after else None))

            belongs = c.get("belongsTo")

            if belongs is not None:

                culture = "culture" in belongs
                fit_before = _fit(a.reading, "culture", before.topics)
                fit_after = _fit(b.reading, "culture", after.topics)

                if fit_before is not None and fit_after is not None:
                    fits_before.append((fit_before, culture))
                    fits_after.append((fit_after, culture))

                    if not culture and fit_before < ranking.GROUP_FIT <= fit_after:
                        pulled.append(brief(c, belongsTo=belongs, fitBefore=round(fit_before, 4), fitAfter=round(fit_after, 4)))

    def auc(pairs: list[tuple[float, bool]]) -> float | None:

        positives = [value for value, label in pairs if label]
        negatives = [value for value, label in pairs if not label]

        if not positives or not negatives:
            return None

        wins = sum(1.0 if p > n else 0.5 if p == n else 0.0 for p in positives for n in negatives)

        return round(wins / (len(positives) * len(negatives)), 4)

    fit_auc = {"before": auc(fits_before), "after": auc(fits_after), "n": len(fits_before)}
    drop = None if fit_auc["before"] is None or fit_auc["after"] is None else round(fit_auc["before"] - fit_auc["after"], 4)

    checks = {
        "leak": {"value": len(leaked), "bound": MAX_LEAK, "holds": len(leaked) <= MAX_LEAK},
        "loss": {"value": len(lost), "bound": MAX_LOSS, "holds": len(lost) <= MAX_LOSS},
        "fit": {"value": drop, "bound": MAX_FIT_DROP, "holds": drop is not None and drop <= MAX_FIT_DROP},
        "pull": {"value": len(pulled), "bound": MAX_PULL, "holds": len(pulled) <= MAX_PULL},
    }

    labelled = Counter(c["hand"] for c in candidates)

    return {
        "rule": "data/evaluation/experiments/topics24/rule.md",
        "candidates": len(candidates),
        "bySet": dict(Counter(c["set"] for c in candidates)),
        "labels": {str(k): labelled[k] for k in (0, 1, 2)},
        "leftOut": {
            "before": sum(1 for a in first if a.verdict is not None),
            "after": sum(1 for b in second if b.verdict is not None),
        },
        "checks": checks,
        "adopt": all(check["holds"] for check in checks.values()),
        "groupFitAuc": fit_auc,
        "changedNearestTopic": changed_nearest,
        "leaked": leaked,
        "lost": lost,
        "pulled": pulled,
        "nearestIsNewTopic": nearest_new,
    }


def topics24_report(result: dict) -> str:

    from src.evaluation.experiments import table

    checks = result["checks"]
    verdict = "**Adopted**: every check holds." if result["adopt"] else "**Not adopted**: " + ", ".join(
        name for name, check in checks.items() if not check["holds"]
    ) + " failed."

    lines = [
        "# internet_culture: 23 topics against 24",
        "",
        f"{result['candidates']} labelled candidates ({', '.join(f'{k}: {v}' for k, v in result['bySet'].items())}); "
        f"labels 0/1/2: {result['labels']['0']}/{result['labels']['1']}/{result['labels']['2']} (Claude's). "
        f"The rule, written before the run: `{result['rule']}`.",
        "",
        verdict,
        "",
        table(["Check", "Measured", "Bound", "Holds"], [
            ("Leak: back in, not worth offering", checks["leak"]["value"], f"<= {checks['leak']['bound']}", checks["leak"]["holds"]),
            ("Loss: newly left out, worth offering", checks["loss"]["value"], f"<= {checks['loss']['bound']}", checks["loss"]["holds"]),
            ("Fit: Culture group-fit AUC drop", checks["fit"]["value"], f"<= {checks['fit']['bound']}", checks["fit"]["holds"]),
            ("Pull: other groups' stories now fitting Culture", checks["pull"]["value"], f"<= {checks['pull']['bound']}", checks["pull"]["holds"]),
        ]),
        "",
        f"Left out by the screen: {result['leftOut']['before']} with 23 topics, {result['leftOut']['after']} with 24. "
        f"Culture group-fit AUC {result['groupFitAuc']['before']} -> {result['groupFitAuc']['after']} "
        f"over {result['groupFitAuc']['n']} candidates. {result['changedNearestTopic']} changed nearest topic.",
        "",
    ]

    for title, key in (
        ("Back in, labelled not worth offering", "leaked"),
        ("Newly left out, labelled worth offering", "lost"),
        ("Other groups' stories now fitting Culture", "pulled"),
        ("Nearest topic now internet_culture (deciding nothing)", "nearestIsNewTopic"),
    ):
        items = result[key]
        lines += [f"## {title} ({len(items)})", ""]
        lines += [f"- [{item['hand']}] {item['title']} ({item['set']})" for item in items] or ["None."]
        lines.append("")

    return "\n".join(lines)


def positive_source_ids() -> set[str]:
    """The configured sources marked positive_editorial: exempt from the screen, as in the app."""

    from src.repositories.source_repository import SourceRepository

    return {source.id for source in SourceRepository().list() if source.positive_editorial}


def run_topics24() -> tuple[dict, str]:

    candidates = load_labelled(positive_sources=positive_source_ids())

    before = MissionScreen(topics=topics_before())
    after = MissionScreen(topics=topics_after())

    result = topics24_experiment(candidates, before, after)

    return result, topics24_report(result)


# ----------------------------------------------------------------------
# trends (T6): five trending rounds labelled blind (RQ1)
# ----------------------------------------------------------------------
#
# The rule, written before the first day: data/evaluation/experiments/
# trends/rule.md. Each day's folder (days/<YYYY-MM-DD>/) holds the
# trending round and the topic rounds as they were made, the first twenty
# to label (to-label.json, no scores, shuffled) and, once labelled,
# labels.json. `trends report` reads every day and the rounds' state now
# (what was chosen since), the lake (what was admitted) and the drafts
# (what was published).

DAYS = EXPERIMENTS / "trends" / "days"

DAYS_PLANNED = 5

FIRST = 20

# The day's topic rounds: the five groups in two, as /discover allows
# three at most.
DAY_GROUPS = (["society", "science", "environment"], ["culture", "health"])

PER_TREND_DAY = 2
PER_SOURCE_DAY = 3

ANGLES = ("story", "possible", "none")

# The rule's bounds for the decisions taken after five days.
MIN_NEW_STORIES = 10
DISABLE_SHARE = 0.8
DISABLE_MIN_LABELLED = 10
REFIT_MIN_LABELLED = 100


def label_items(round_: dict, first: int = FIRST) -> list[dict]:
    """
    The trending round's first twenty as a person reads them before
    choosing - title, summary, outlet, trend - with nothing of the score,
    the rank, the reading or the AI. Shuffled by a hash of the link, so the
    order is not the ranking's.
    """

    import hashlib

    items = [
        {
            "url": candidate["url"],
            "title": candidate.get("title"),
            "summary": candidate.get("summary"),
            "outlet": candidate.get("sourceName"),
            "language": candidate.get("language"),
            "trend": (candidate.get("trend") or {}).get("name"),
            "signal": (candidate.get("trend") or {}).get("signalName"),
        }
        for candidate in round_["candidates"][:first]
    ]

    items.sort(key=lambda item: hashlib.sha1(item["url"].encode("utf-8")).hexdigest())

    for number, item in enumerate(items, start=1):
        item["n"] = number

    return items


def trends_day(selection, day: str, root: Path = DAYS, force: bool = False) -> Path:
    """
    A day's three rounds through the app's own selection service - saved
    where /discover keeps its rounds, so a person can choose from them -
    and the day's folder. At most one a day (rule.md): refused when the
    day has run, unless `force`.
    """

    folder = Path(root) / day

    if (folder / "rounds.json").exists() and not force:
        raise SystemExit(f"Day {day} has already run ({folder}). The rule says one round a day.")

    trending = selection.create_round([], None, PER_TREND_DAY, listed=FIRST, trending=True)
    topics = [selection.create_round(groups, None, PER_SOURCE_DAY, listed=FIRST) for groups in DAY_GROUPS]

    folder.mkdir(parents=True, exist_ok=True)

    def save(name: str, data) -> None:
        (folder / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    save("rounds.json", {
        "day": day,
        "trendingRound": trending["id"],
        "topicRounds": [round_["id"] for round_ in topics],
        "rule": "data/evaluation/experiments/trends/rule.md",
        "settings": {"perTrend": PER_TREND_DAY, "perSource": PER_SOURCE_DAY, "search": False, "dayGroups": DAY_GROUPS},
    })
    save("trending-round.json", trending)
    save("topic-rounds.json", topics)
    save("to-label.json", {
        "day": day,
        "how": "Label each from what it shows, before looking at the round's scores: hand 0/1/2 "
               "(not worth offering / worth offering / clearly positive), angle story/possible/none, "
               "private true when its subject is a private person or a child in a video. rule.md.",
        "items": label_items(trending),
    })

    return folder


def load_days(root: Path = DAYS) -> list[dict]:
    """Every day's folder: its rounds as made, and its labels when there are any."""

    days = []

    for folder in sorted(Path(root).glob("*/")):

        if not (folder / "rounds.json").exists():
            continue

        def read(name: str):
            path = folder / name
            return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

        days.append({
            "day": folder.name,
            "rounds": read("rounds.json"),
            "trending": read("trending-round.json"),
            "topics": read("topic-rounds.json") or [],
            "labels": read("labels.json"),
        })

    return days


def _new_story(url: str, title: str | None, topic_urls: set[str], topic_titles: list[str], similar) -> bool:
    """Not offered by a topic round that day: not by host and path, nor (with `similar`) as the same story."""

    if comparable_url(url) in topic_urls:
        return False

    if similar is None or not title or not topic_titles:
        return True

    return similar(title, topic_titles) < ranking.SAME_STORY


def _funnel(day: dict, rounds_now: dict, admitted: dict[str, bool], published: set[str]) -> dict:

    round_ = day["trending"] or {}
    totals = round_.get("totals") or {}
    now = rounds_now.get(round_.get("id")) or round_
    chosen = list((now.get("queued") or {}).get("urls") or [])

    passed = totals.get("discovered", 0) - totals.get("notArticles", 0) - totals.get("stale", 0) - totals.get("alreadyStored", 0)

    return {
        "trends": totals.get("trends", 0),
        "articles": totals.get("discovered", 0),
        "passedLinkFilters": passed,
        "keptByScreen": passed - totals.get("screened", 0),
        "offered": totals.get("candidates", 0),
        "shown": len(round_.get("candidates") or []),
        "chosen": len(chosen),
        "admitted": sum(1 for url in chosen if admitted.get(comparable_url(url))),
        "published": sum(1 for trend in round_.get("trends") or [] if trend.get("id") in published),
    }


def trends_experiment(
    days: list[dict],
    similar=None,
    rounds_now: dict | None = None,
    admitted: dict[str, bool] | None = None,
    published: set[str] | None = None,
) -> dict:
    """
    The rule's report over the days run so far. `similar(title, titles)` is
    the highest title similarity (None: by link only). `rounds_now` are the
    rounds as they stand (chosen since), `admitted` what the lake admitted
    by host and path, `published` the trend ids a published draft came from.
    """

    from src.evaluation.experiments import interval

    rounds_now = rounds_now or {}
    admitted = admitted or {}
    published = published or set()

    per_day = []
    by_signal: dict[str, Counter] = {}
    pooled = Counter()
    new_stories_total = 0
    labelled_total = 0

    for day in days:

        funnel = _funnel(day, rounds_now, admitted, published)
        labels = ((day.get("labels") or {}).get("labels")) or {}
        first = (day["trending"] or {}).get("candidates", [])[:FIRST]

        entry = {"day": day["day"], "funnel": funnel, "labelled": 0}

        if labels:

            topic_urls = {
                comparable_url(candidate["url"])
                for round_ in day["topics"]
                for candidate in (round_.get("candidates") or []) + (round_.get("reserve") or [])
            }
            topic_titles = [
                candidate.get("title") or ""
                for round_ in day["topics"]
                for candidate in (round_.get("candidates") or []) + (round_.get("reserve") or [])
            ]

            hands = Counter()
            angles = Counter()
            private = 0
            new = []

            for candidate in first:

                label = labels.get(candidate["url"])

                if not label or label.get("hand") is None:
                    continue

                hand = int(label["hand"])
                hands[hand] += 1
                angles[label.get("angle") or "none"] += 1
                private += bool(label.get("private"))

                signal = (candidate.get("trend") or {}).get("signalName") or "?"
                by_signal.setdefault(signal, Counter())[hand] += 1

                if hand >= 1 and _new_story(candidate["url"], candidate.get("title"), topic_urls, topic_titles, similar):
                    new.append({"url": candidate["url"], "title": candidate.get("title"), "hand": hand})

            n = sum(hands.values())
            labelled_total += n
            new_stories_total += len(new)
            pooled.update(hands)

            entry.update({
                "labelled": n,
                "labelledBy": (day.get("labels") or {}).get("labelledBy"),
                "worthOffering": hands[1] + hands[2],
                "clearlyPositive": hands[2],
                "precision": round((hands[1] + hands[2]) / n, 4) if n else None,
                "clearlyPositiveShare": round(hands[2] / n, 4) if n else None,
                "angles": {angle: angles[angle] for angle in ANGLES},
                "private": private,
                "newStories": new,
                "topicCandidates": len(topic_urls),
            })

        per_day.append(entry)

    labelled_days = [entry for entry in per_day if entry["labelled"]]
    remaining = max(0, DAYS_PLANNED - len(labelled_days))

    signals = {
        signal: {
            "labelled": sum(counts.values()),
            "notWorth": counts[0],
            "worth": counts[1],
            "clearlyPositive": counts[2],
            "notWorthShare": round(counts[0] / sum(counts.values()), 4) if sum(counts.values()) else None,
        }
        for signal, counts in sorted(by_signal.items())
    }

    decisions = None

    if not remaining:
        decisions = {
            "lensStays": new_stories_total >= MIN_NEW_STORIES,
            "disableSignals": [
                signal for signal, row in signals.items()
                if row["labelled"] >= DISABLE_MIN_LABELLED and row["notWorthShare"] >= DISABLE_SHARE
            ],
            "refitWeights": labelled_total >= REFIT_MIN_LABELLED,
        }

    return {
        "rule": "data/evaluation/experiments/trends/rule.md",
        "daysRun": len(per_day),
        "daysLabelled": len(labelled_days),
        "daysRemaining": remaining,
        "sameStoryBy": "title similarity" if similar is not None else "link only",
        "precision": interval([entry["precision"] for entry in labelled_days]) if labelled_days else None,
        "clearlyPositive": interval([entry["clearlyPositiveShare"] for entry in labelled_days]) if labelled_days else None,
        "newStories": new_stories_total,
        "labelled": labelled_total,
        "pooled": {str(hand): pooled[hand] for hand in (0, 1, 2)},
        "bySignal": signals,
        "days": per_day,
        "decisions": decisions,
    }


def trends_report(result: dict) -> str:

    from src.evaluation.experiments import table

    lines = [
        "# Trending rounds, labelled blind (RQ1)",
        "",
        f"The rule, written before day 1: `{result['rule']}`. {result['daysLabelled']} of {DAYS_PLANNED} days "
        f"labelled, **{result['daysRemaining']} to go**: one a day with "
        "`uv run python -m src.evaluation.experiments trends run`, then label `to-label.json` into `labels.json`, "
        "then `trends report`. New stories are told from the topic rounds' "
        f"by {result['sameStoryBy']}.",
        "",
    ]

    if result["precision"]:
        lines += [
            f"First twenty worth offering or clearly positive: {result['precision']['mean']} "
            f"[{result['precision']['low']}, {result['precision']['high']}] a day; clearly positive "
            f"{result['clearlyPositive']['mean']}. {result['newStories']} stories worth offering no topic round "
            f"offered the same day, of {result['labelled']} labelled.",
            "",
        ]

    lines += [
        table(
            ["Day", "Trends", "Articles", "Kept by screen", "Offered", "Chosen", "Admitted", "Published",
             "Labelled", "Worth offering", "Clearly positive", "New stories", "Private subject"],
            [
                (
                    entry["day"], entry["funnel"]["trends"], entry["funnel"]["articles"], entry["funnel"]["keptByScreen"],
                    entry["funnel"]["offered"], entry["funnel"]["chosen"], entry["funnel"]["admitted"],
                    entry["funnel"]["published"], entry["labelled"], entry.get("worthOffering"),
                    entry.get("clearlyPositive"), len(entry.get("newStories") or []), entry.get("private"),
                )
                for entry in result["days"]
            ],
        ),
        "",
        "## By signal (first twenties)",
        "",
        table(
            ["Signal", "Labelled", "Not worth", "Worth", "Clearly positive", "Not-worth share"],
            [(name, row["labelled"], row["notWorth"], row["worth"], row["clearlyPositive"], row["notWorthShare"])
             for name, row in result["bySignal"].items()],
        ),
        "",
    ]

    for entry in result["days"]:
        if entry.get("newStories"):
            lines += [f"## New stories, {entry['day']}", ""]
            lines += [f"- [{item['hand']}] {item['title']}" for item in entry["newStories"]]
            lines.append("")

    if result["decisions"] is None:
        lines.append(f"Nothing is decided before the five days ({result['daysRemaining']} to go).")
    else:
        decisions = result["decisions"]
        lines += [
            "## Decisions (rule.md)",
            "",
            f"- The lens stays on /discover: {'yes' if decisions['lensStays'] else 'no, the author decides'} "
            f"({result['newStories']} new stories, {MIN_NEW_STORIES} needed).",
            f"- Signals disabled by default: {', '.join(decisions['disableSignals']) or 'none'}.",
            f"- Refit the trend weights: {'yes' if decisions['refitWeights'] else 'no'} "
            f"({result['labelled']} labelled, {REFIT_MIN_LABELLED} needed).",
        ]

    labelled_by = {entry.get("labelledBy") for entry in result["days"] if entry.get("labelledBy")}
    if labelled_by:
        lines += ["", f"Labelled by: {', '.join(sorted(labelled_by))}."]

    return "\n".join(lines) + "\n"


def title_similarity():
    """`similar` for trends_experiment: the best cosine between a title and others, over inference/."""

    import numpy as np

    from src.services.embeddings.service import EmbeddingService

    service = EmbeddingService()
    cache: dict[str, np.ndarray] = {}

    def vectors(texts: list[str]) -> list:
        missing = [text for text in dict.fromkeys(texts) if text not in cache]
        if missing:
            for text, vector in zip(missing, service.encode_many(missing)):
                cache[text] = np.asarray(vector)
        return [cache[text] for text in texts]

    def similar(title: str, titles: list[str]) -> float:
        [mine] = vectors([title])
        others = vectors([text for text in titles if text])
        return max((float(mine @ other) for other in others), default=0.0)

    return similar


def _attach_app_stores() -> None:
    """Where the app keeps its rounds, sightings, request counts and trend ledger: what main.py attaches."""

    from src.config.settings import settings
    from src.services.scraper.request_stats import request_stats
    from src.services.scraper.sightings import sightings
    from src.services.selection.rounds import selection_rounds
    from src.services.trends.ledger import trend_ledger

    request_stats.attach(settings.LAKE_PATH / "stats" / "scraper_requests.json")
    sightings.attach(settings.LAKE_PATH / "stats" / "sightings.json")
    selection_rounds.attach(settings.LAKE_PATH / "stats" / "selection")
    trend_ledger.attach(settings.LAKE_PATH / "stats" / "trends" / "articles.json")


def run_trends_day(force: bool = False) -> Path:

    from datetime import datetime, timezone

    from src.container import get_selection_service

    _attach_app_stores()

    return trends_day(get_selection_service(), datetime.now(timezone.utc).strftime("%Y-%m-%d"), force=force)


def run_trends_report() -> tuple[dict, str]:

    from src.container import get_datalake_repository, get_draft_store, get_selection_service
    from src.models.storage.lineage import DataLayer

    _attach_app_stores()

    days = load_days()
    selection = get_selection_service()

    rounds_now = {}
    for day in days:
        for round_id in [(day["rounds"] or {}).get("trendingRound")] + list((day["rounds"] or {}).get("topicRounds") or []):
            try:
                rounds_now[round_id] = selection.get(round_id)
            except Exception:  # noqa: BLE001 - a round no longer on disk is reported as it was made
                continue

    admitted = {}
    for record in get_datalake_repository().list(DataLayer.PROCESSED):
        url = (record.get("lineage") or {}).get("source_url")
        if url:
            admitted[comparable_url(url)] = bool((record.get("fact_check") or {}).get("validation_passed"))

    published = set()
    for draft in get_draft_store().list():
        trend = getattr(draft, "trend", None)
        if draft.status == "published" and trend:
            published.add(trend.get("id") if isinstance(trend, dict) else getattr(trend, "id", None))

    try:
        similar = title_similarity()
        similar("probe", ["probe"])
    except Exception:  # noqa: BLE001 - inference/ down: new stories by link only, and the report says so
        similar = None

    result = trends_experiment(days, similar, rounds_now, admitted, published)

    return result, trends_report(result)
