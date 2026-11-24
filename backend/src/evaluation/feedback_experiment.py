"""
`experiments feedback`: does what a person rejects teach the ranking?
(src/services/selection/feedback.py, 2026-11-24)

Every hand-labelled candidate of 6, 9 and 13 Oct that the screen kept -
0 not worth offering, 1 worth offering, 2 clearly positive - plays a
person: one day's 0s are what they rejected and its 2s what they chose,
and the rule runs on the other days' candidates. Three questions:

1. **Does nearness to one rejected story generalise?** Left out when a
   candidate comes within a floor of any rejected story (and, with a
   margin, nearer it than any chosen one).
2. **Does lowering by the lean help the order?** The AUC of the story part
   (ranking.NEWS_RANGE, scaled as the ranking scales it) without and with
   the lean taken off at several weights - telling the worth-offering
   from the rest, and the clearly positive from the rest - over draws of
   3 to 40 rejected examples, as a person would give them.
3. **What would leaving out cost?** At several lean margins, how many of
   each label go, on average and in the worst draw.

Needs inference/ (bge-m3, and the mission screen's readings). Seeded, so a
re-run gives the same draws. The labels are an AI's (Claude's), not yet a
person's; the person's own rejections are what the rule runs on.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np

from src.evaluation.experiments import EXPERIMENTS, auc, table
from src.services.selection import ranking
from src.services.selection.feedback import LEAN_WEIGHTS, LEAVE_OUT_LEAN, LEAVE_OUT_MINIMUM, LOWER_MINIMUM
from src.services.selection.mission_screen import Candidate, MissionScreen, screen_text

SETS = (
    (EXPERIMENTS / "ranking" / "20261006T133348Z" / "result.json", "6 Oct"),
    (EXPERIMENTS / "alignment" / "20261009T120000Z" / "labelled.json", "9 Oct"),
    (EXPERIMENTS / "emphasis" / "reserve-labels.json", "13 Oct"),
)

SEED = 20261124
DRAWS = 200
SIZES = ((3, 3), (5, 3), (10, 5), (20, 10), (40, 20))
WEIGHTS = (0.25, 0.5, 1.0)
MARGINS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)
FLOORS = (0.60, 0.65, 0.70, 0.75, 0.80)


def load(sets=SETS) -> list[dict]:
    """The labelled candidates the screen kept, once each, with what to embed."""

    rows, seen = [], set()

    for path, day in sets:
        for item in json.loads(Path(path).read_text(encoding="utf-8"))["candidates"]:
            text = screen_text(item.get("title"), item.get("summary"))
            if item.get("left_out") or item.get("hand") is None or not text or item["url"] in seen:
                continue
            seen.add(item["url"])
            rows.append({
                "url": item["url"], "title": item.get("title"), "summary": item.get("summary"),
                "language": item.get("lang") or "en", "text": text, "hand": int(item["hand"]), "day": day,
            })

    return rows


def read(rows: list[dict], screen: MissionScreen | None = None) -> list[dict]:
    """
    Each row with its unit vector and its story reading (impact - nearest
    off-mission), from inference/. A row today's screen decides by its
    headline alone (a format, a death) has no reading and is dropped: it
    would not be offered.
    """

    screen = screen or MissionScreen()
    assessments = screen.assess([Candidate(title=r["title"], summary=r["summary"], language=r["language"]) for r in rows])
    kept = []

    for row, assessment in zip(rows, assessments):
        reading = assessment.reading
        if reading is None or reading.vector is None:
            continue
        vector = np.asarray(reading.vector, dtype=float)
        kept.append({**row, "v": vector / np.linalg.norm(vector), "story": reading.impact - reading.off})

    return kept


def _centroid(rows: list[dict]) -> np.ndarray:

    mean = np.mean([row["v"] for row in rows], axis=0)

    return mean / np.linalg.norm(mean)


def leans(rejected: list[dict], chosen: list[dict], targets: list[dict]) -> np.ndarray:

    away, toward = _centroid(rejected), _centroid(chosen)

    return np.array([t["v"] @ away - t["v"] @ toward for t in targets])


def _aucs(values, targets) -> tuple[float, float]:

    worth = auc([v for v, t in zip(values, targets) if t["hand"] >= 1], [v for v, t in zip(values, targets) if t["hand"] == 0])
    positive = auc([v for v, t in zip(values, targets) if t["hand"] == 2], [v for v, t in zip(values, targets) if t["hand"] < 2])

    return round(worth, 4), round(positive, 4)


def _story_part(targets, lean=None, weight=0.0) -> list[float]:
    """The story part as ranking.news_part scales it, with `weight` of the lean taken off."""

    lean = np.zeros(len(targets)) if lean is None else lean

    return [ranking._scaled(t["story"] - weight * l, ranking.NEWS_RANGE) for t, l in zip(targets, lean)]


def _hands(targets) -> dict:

    return {h: sum(t["hand"] == h for t in targets) for h in (0, 1, 2)}


def _left_out(mask, targets) -> list[int]:

    return [sum(1 for m, t in zip(mask, targets) if m and t["hand"] == h) for h in (0, 1, 2)]


def nearest_neighbour(rejected, chosen, targets) -> list[dict]:

    R = np.array([r["v"] for r in rejected])
    C = np.array([r["v"] for r in chosen])
    near_rejected = np.array([float((R @ t["v"]).max()) for t in targets])
    near_chosen = np.array([float((C @ t["v"]).max()) for t in targets])

    return [
        {"floor": floor, "margin": margin, "leftOut": _left_out(
            (near_rejected >= floor) & ((near_rejected - near_chosen > margin) if margin is not None else True), targets,
        )}
        for floor in FLOORS for margin in (None, 0.0)
    ]


def one_way(name, rejected, chosen, targets) -> dict:

    L = leans(rejected, chosen, targets)

    return {
        "name": name,
        "examples": {"rejected": len(rejected), "chosen": len(chosen)},
        "candidates": _hands(targets),
        "nearestNeighbour": nearest_neighbour(rejected, chosen, targets),
        "aucStory": _aucs(_story_part(targets), targets),
        "aucLowered": {str(w): _aucs(_story_part(targets, L, w), targets) for w in WEIGHTS},
        "leaveOut": {str(m): _left_out(L > m, targets) for m in MARGINS},
    }


def draws(pool_day: str, rows: list[dict]) -> list[dict]:
    """A person's few examples, drawn from one day, on the other days' candidates."""

    rng = random.Random(SEED)
    pool = [r for r in rows if r["day"] == pool_day]
    targets = [r for r in rows if r["day"] != pool_day]
    bad, good = [r for r in pool if r["hand"] == 0], [r for r in pool if r["hand"] == 2]
    base = _aucs(_story_part(targets), targets)
    out = []

    for n_rejected, n_chosen in SIZES:

        aucs = {str(w): [] for w in WEIGHTS}
        removed = {str(m): [] for m in MARGINS}

        for _ in range(DRAWS):
            L = leans(rng.sample(bad, n_rejected), rng.sample(good, n_chosen), targets)
            for w in WEIGHTS:
                aucs[str(w)].append(_aucs(_story_part(targets, L, w), targets))
            for m in MARGINS:
                removed[str(m)].append(_left_out(L > m, targets))

        out.append({
            "rejected": n_rejected, "chosen": n_chosen, "draws": DRAWS,
            "aucStory": base,
            "aucLowered": {
                w: {
                    "worth": round(float(np.mean([a[0] for a in values])), 4),
                    "worth5th": round(float(np.percentile([a[0] for a in values], 5)), 4),
                    "positive": round(float(np.mean([a[1] for a in values])), 4),
                    "positive5th": round(float(np.percentile([a[1] for a in values], 5)), 4),
                }
                for w, values in aucs.items()
            },
            "leaveOut": {
                m: {
                    "mean": [round(float(np.mean([v[h] for v in values])), 1) for h in (0, 1, 2)],
                    "worstClearlyPositive": int(max(v[2] for v in values)),
                }
                for m, values in removed.items()
            },
        })

    return {"pool": pool_day, "candidates": _hands(targets), "sizes": out}


def feedback_experiment(rows: list[dict]) -> dict:

    first = [r for r in rows if r["day"] == "6 Oct"]
    later = [r for r in rows if r["day"] != "6 Oct"]

    return {
        "labelledBy": "Claude (AI), not yet checked by a person: 0 not worth offering, 1 worth offering, 2 clearly positive",
        "candidates": _hands(rows),
        "rule": {
            "weights": [list(step) for step in LEAN_WEIGHTS], "leaveOutLean": LEAVE_OUT_LEAN,
            "lowerMinimum": LOWER_MINIMUM, "leaveOutMinimum": LEAVE_OUT_MINIMUM,
        },
        "oneWay": [
            one_way("6 Oct teaches 9 and 13 Oct", [r for r in first if r["hand"] == 0], [r for r in first if r["hand"] == 2], later),
            one_way("9 and 13 Oct teach 6 Oct", [r for r in later if r["hand"] == 0], [r for r in later if r["hand"] == 2], first),
        ],
        "draws": draws("9 Oct", rows),
        "seed": SEED,
    }


def feedback_report(result: dict) -> str:

    hands = lambda h: f"{h[0]} / {h[1]} / {h[2]}"
    lines = [
        "# What the person rejects: does it teach the ranking?",
        "",
        f"{sum(result['candidates'].values())} hand-labelled candidates the screen kept (not worth offering / worth offering /",
        f"clearly positive: {hands(result['candidates'])}). {result['labelledBy']}. One day's 0s play what a person rejected, its 2s",
        "what they chose; the rule runs on the other days. The rule as built: lowered by "
        + ", ".join(f"{w} of the lean from {r} + {c} examples" for r, c, w in result["rule"]["weights"]) + "; "
        f"left out over {result['rule']['leaveOutLean']} from {result['rule']['leaveOutMinimum'][0]} + {result['rule']['leaveOutMinimum'][1]}.",
        "",
    ]

    for way in result["oneWay"]:
        lines += [
            f"## {way['name']} ({way['examples']['rejected']} rejected, {way['examples']['chosen']} chosen; candidates {hands(way['candidates'])})",
            "",
            "Nearest neighbour: left out when within the floor of a rejected story (and nearer it than any chosen, with a margin).",
            "",
            table(["Floor", "Margin", "Not worth", "Worth", "Clearly positive"],
                  [(row["floor"], row["margin"], *row["leftOut"]) for row in way["nearestNeighbour"]]),
            "",
            f"AUC of the story part, worth vs not / clearly positive vs rest: alone {way['aucStory'][0]} / {way['aucStory'][1]}; "
            + "; ".join(f"lowered by {w} of the lean {a[0]} / {a[1]}" for w, a in way["aucLowered"].items()) + ".",
            "",
            table(["Left out over lean", "Not worth", "Worth", "Clearly positive"],
                  [(m, *counts) for m, counts in way["leaveOut"].items()]),
            "",
        ]

    d = result["draws"]
    lines += [
        f"## A person's few examples: drawn from {d['pool']}, {d['sizes'][0]['draws']} draws each, on the other days (candidates {hands(d['candidates'])})",
        "",
        "AUC of the story part, mean [5th percentile].",
        "",
        table(
            ["Rejected + chosen", "Story alone (worth / positive)", *[f"Lowered by {w}: worth" for w in WEIGHTS], *[f"Lowered by {w}: positive" for w in WEIGHTS]],
            [
                (f"{s['rejected']} + {s['chosen']}", f"{s['aucStory'][0]} / {s['aucStory'][1]}",
                 *[f"{s['aucLowered'][str(w)]['worth']} [{s['aucLowered'][str(w)]['worth5th']}]" for w in WEIGHTS],
                 *[f"{s['aucLowered'][str(w)]['positive']} [{s['aucLowered'][str(w)]['positive5th']}]" for w in WEIGHTS])
                for s in d["sizes"]
            ],
        ),
        "",
        "Left out over a lean: mean not worth / worth / clearly positive per draw, and the most clearly positive lost in any draw.",
        "",
        table(
            ["Rejected + chosen", *[f"lean > {m}" for m in MARGINS]],
            [
                (f"{s['rejected']} + {s['chosen']}",
                 *[f"{v['mean'][0]} / {v['mean'][1]} / {v['mean'][2]} (worst {v['worstClearlyPositive']})" for v in s["leaveOut"].values()])
                for s in d["sizes"]
            ],
        ),
        "",
    ]

    return "\n".join(lines)


def run_feedback() -> tuple[dict, str]:

    rows = read(load())
    result = feedback_experiment(rows)

    return result, feedback_report(result)
