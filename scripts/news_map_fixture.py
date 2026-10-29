"""
A synthetic news map for N8's rendering budget (docs/goals.md, N8): n
published stories placed by the real layout (backend/src/services/
news_map/layout.py), as GET /map/articles sends them, deterministic by
seed.

    cd backend && uv run python ../scripts/news_map_fixture.py 10000 > /tmp/map-10k.json

Topics are drawn unevenly, as a real corpus is (a Dirichlet over the 23);
a fifth of the stories tie a second topic; vectors are random unit
vectors pulled towards one of 40 story directions per topic, so clusters
have structure. Titles are as long as real ones (60-110 characters),
since the payload's size is mostly titles. Each story names up to five
of n/4 people.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.config.topics import TOPICS  # noqa: E402
from src.services.news_map.layout import GROUP_ORDER, anchors, frame, place  # noqa: E402

WORDS = ("community", "garden", "river", "school", "volunteers", "solar", "library", "clinic", "forest",
         "students", "rescue", "museum", "wetland", "reef", "village", "market", "bridge", "festival")


def fixture(count: int, seed: int = 1) -> dict:

    rng = np.random.default_rng(seed)
    keys = list(anchors())
    weights = rng.dirichlet(np.ones(len(keys)) * 0.8)
    directions = {k: rng.standard_normal((40, 1024)) for k in keys}
    people = max(1, count // 4)

    columns = {name: [] for name in ("id", "title", "lang", "day", "src", "g", "t", "e", "v", "x", "y", "z", "approx")}
    entities = [{"k": f"person:person {i}", "n": f"Person {i}", "t": "person"} for i in range(people)]

    for i in range(count):

        key = keys[rng.choice(len(keys), p=weights)]
        topics = [{"topic": TOPICS[key].name, "confidence": 0.4}]
        if rng.random() < 0.2:
            other = keys[rng.integers(len(keys))]
            topics.append({"topic": TOPICS[other].name, "confidence": 0.4 - rng.random() * 0.06})

        vector = directions[key][rng.integers(40)] + 0.7 * rng.standard_normal(1024)
        placed = place(f"{i:016x}", topics, list(vector))

        words = " ".join(rng.choice(WORDS, size=rng.integers(7, 13)))
        columns["id"].append(f"{i:016x}")
        columns["title"].append(f"{TOPICS[key].name}: {words}"[:110])
        columns["lang"].append("es" if rng.random() < 0.4 else "en")
        columns["day"].append(f"2026-10-{1 + int(rng.integers(29)):02d}")
        columns["src"].append(int(rng.integers(32)))
        columns["g"].append(GROUP_ORDER.index(placed.group))
        columns["t"].append([keys.index(t) for t in placed.topics])
        columns["e"].append(sorted({int(j) for j in rng.integers(0, people, rng.integers(0, 6))}))
        columns["v"].append("TRUE" if rng.random() < 0.7 else "UNVERIFIED")
        columns["x"].append(round(placed.x, 4))
        columns["y"].append(round(placed.y, 4))
        columns["z"].append(round(placed.z, 4))
        columns["approx"].append(None)

    return {
        **frame(),
        "day": None,
        "count": count,
        "sources": [f"Outlet {i}" for i in range(32)],
        "entities": entities,
        "articles": columns,
    }


if __name__ == "__main__":
    print(json.dumps(fixture(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 1), separators=(",", ":")))
