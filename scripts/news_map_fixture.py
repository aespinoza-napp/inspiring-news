"""
A synthetic news map for N8's rendering budget (docs/goals.md, N8) and
the previews: n published stories placed by the real layout
(backend/src/services/news_map/layout.py), as GET /map/articles sends
them, deterministic by seed.

    cd backend && uv run python ../scripts/news_map_fixture.py 10000 > /tmp/map-10k.json

Topics are drawn unevenly, as a real corpus is (a Dirichlet over the 23);
a fifth of the stories tie a second topic; vectors are random unit
vectors pulled towards one of 40 story directions per topic, so clusters
have structure. Titles are as long as real ones (60-110 characters),
since the payload's size is mostly titles.

Names, as GLiNER types them: real places (cities and countries), and
fictional companies, people and brands - the preview must not put a real
person or company in a story nobody wrote. Each story names one to four,
most often a place; within each kind a few are named often and most
rarely (Zipf), so the network has hubs as real news does. Each name has
home topics (places several, a company or a person one or two), and a
story names someone from its own topic AFFINITY of the time and anyone
otherwise: names cluster round what they are about, with exceptions. Stories arrive
about STORIES_PER_DAY a day, back from today, as the newsroom publishes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from src.config.topics import TOPICS  # noqa: E402
from src.services.graph.graph_writer import entity_key  # noqa: E402
from src.services.news_map.days import today  # noqa: E402
from src.services.news_map.layout import GROUP_ORDER, anchors, frame, place  # noqa: E402

from datetime import timedelta  # noqa: E402

STORIES_PER_DAY = 45

CITIES = ("Barcelona", "Madrid", "Valencia", "Seville", "Bilbao", "Lisbon", "Paris", "Berlin", "London", "Nairobi",
          "Lagos", "Cape Town", "Mumbai", "Tokyo", "Seoul", "Sydney", "Bogotá", "Lima", "Mexico City", "Buenos Aires",
          "São Paulo", "New York", "Toronto", "Vancouver", "Oslo", "Copenhagen", "Amsterdam", "Kyoto", "Manila",
          "Jakarta", "Dakar", "Accra", "Kigali", "Reykjavik", "Helsinki", "Vienna", "Zurich", "Athens", "Marrakesh")
COUNTRIES = ("Spain", "Kenya", "Japan", "Brazil", "Canada", "India", "Norway", "Chile", "Portugal", "Rwanda")
COMPANIES = ("Solaris Grid", "BlueTide Labs", "Verdana Foods", "Kinetic Rail", "OpenHarvest", "Aurora Health",
             "Nimbus Water", "TerraCycle Works", "Lumen Bio", "Atlas Robotics", "Coralis Marine", "Greenway Mobility",
             "Helio Glass", "Quanta Clinics", "Riverstone Energy", "Seedline Agro", "UrbanLoop", "Vita Genomics",
             "WindForge", "Zephyr Air")
PEOPLE = ("Ana Ruiz", "Kofi Mensah", "Mei Tanaka", "Lucas Ferreira", "Amara Diallo", "Elena Petrova", "Rahul Mehta",
          "Sofia Lindqvist", "Diego Morales", "Aiko Sato", "Grace Okafor", "Marta Vidal", "Jonas Berg", "Leila Haddad",
          "Tomás Ortega", "Nadia Rahman", "Pablo Serra", "Hannah Weber", "Yuki Mori", "Carmen Soto")
BRANDS = ("EcoPack", "SunBottle", "AquaPure", "GreenBike", "LeafPhone", "SolarKit", "ReFill", "NovaShoe",
          "CleanAir One", "TerraBrick")

# (GLiNER type, names, how often a story names one of them, how many home
# topics each name has: places are named across topics, a company or a
# person mostly in one or two, a brand in one).
KINDS = (("city", CITIES, 0.55, (2, 5)), ("country", COUNTRIES, 0.2, (3, 7)), ("company", COMPANIES, 0.4, (1, 3)),
         ("person", PEOPLE, 0.35, (1, 3)), ("product", BRANDS, 0.15, (1, 2)))

# How often a story names someone from its own topic rather than anyone:
# real names cluster around what they are about, with exceptions.
AFFINITY = 0.8

WORDS = ("community", "garden", "river", "school", "volunteers", "solar", "library", "clinic", "forest",
         "students", "rescue", "museum", "wetland", "reef", "village", "market", "bridge", "festival")


def fixture(count: int, seed: int = 1) -> dict:

    rng = np.random.default_rng(seed)
    keys = list(anchors())
    weights = rng.dirichlet(np.ones(len(keys)) * 0.8)
    directions = {k: rng.standard_normal((40, 1024)) for k in keys}
    # Each name's home topics, drawn once; per kind and topic, the names at
    # home there with their popularity.
    pools = []
    for kind, names, chance, (fewest, most) in KINDS:
        rank = np.arange(1, len(names) + 1)
        popularity = 1 / rank ** 1.1
        popularity = popularity / popularity.sum()
        homes = [set(rng.choice(len(keys), size=int(rng.integers(fewest, most)), replace=False)) for _ in names]
        at_home = {}
        for topic in range(len(keys)):
            local = [j for j, home in enumerate(homes) if topic in home]
            if local:
                at_home[topic] = (local, popularity[local] / popularity[local].sum())
        pools.append((kind, names, chance, popularity, at_home))

    entities: list[dict] = []
    entity_ref: dict[str, int] = {}

    def ref(kind: str, name: str) -> int:
        key = entity_key(kind, name)
        if key not in entity_ref:
            entity_ref[key] = len(entities)
            entities.append({"k": key, "n": name, "t": kind})
        return entity_ref[key]

    last = today()
    span = max(1, count // STORIES_PER_DAY)

    columns = {name: [] for name in ("id", "title", "lang", "day", "src", "g", "t", "e", "v", "x", "y", "z", "approx")}

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
        columns["day"].append((last - timedelta(days=int(rng.integers(span)))).isoformat())
        columns["src"].append(int(rng.integers(32)))
        columns["g"].append(GROUP_ORDER.index(placed.group))
        columns["t"].append([keys.index(t) for t in placed.topics])
        main = keys.index(key)
        named = []
        for kind, names, chance, popularity, at_home in pools:
            if rng.random() >= chance:
                continue
            if main in at_home and rng.random() < AFFINITY:
                local, local_popularity = at_home[main]
                named.append(ref(kind, names[local[rng.choice(len(local), p=local_popularity)]]))
            else:
                named.append(ref(kind, names[rng.choice(len(names), p=popularity)]))
        columns["e"].append(sorted(set(named))[:5])
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
