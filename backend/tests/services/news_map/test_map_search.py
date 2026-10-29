import numpy as np
import pytest

from src.config.topics import TOPICS
from src.services.inference_client import InferenceUnavailable
from src.services.news_map.index import MapIndex
from src.services.news_map.search import (
    MAX_QUERY,
    SEMANTIC_PER_MINUTE,
    MapSearch,
    RateLimited,
    RateLimiter,
    fold,
)
from src.services.reader.index import ReaderIndex
from src.services.reader.views import SourceNames

from tests.services.reader.reader_lake import make_lake, publish


def unit(seed: int) -> list[float]:
    vector = np.random.default_rng(seed).standard_normal(1024)
    return list(vector / np.linalg.norm(vector))


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def index(tmp_path):
    lake = make_lake(tmp_path)
    return MapIndex(lake, ReaderIndex(lake), SourceNames())


def put(index, slug, title, topic="climate", seed=0, **kwargs):
    return publish(
        index.lake,
        f"https://www.bbc.com/news/{slug}-a-story-long-enough",
        title=title,
        topics=[(TOPICS[topic].name, 0.6)],
        embedding=unit(seed),
        **kwargs,
    )


def test_folding_drops_case_accents_and_punctuation():

    assert fold("  Barça,  CAMPEÓN! ") == "barca campeon"
    assert fold("Ada  Lovelace") == "ada lovelace"


def test_barca_finds_barca_with_its_cedilla(index):

    put(index, "one", "El Barça gana la liga", entities={"organization": ["Barça"]})

    results = MapSearch(index).search("barca", "client", semantic=False)["results"]

    assert results[0]["kind"] == "entity"
    assert results[0]["name"] == "Barça"


def test_a_misspelt_name_is_found_by_its_trigrams(index):

    put(index, "one", "Notes on engines", entities={"person": ["Ada Lovelace"]})

    names = [r["name"] for r in MapSearch(index).search("Ada Lovelase", "c", semantic=False)["results"] if r["kind"] == "entity"]

    assert names == ["Ada Lovelace"]


def test_a_spanish_query_finds_the_spanish_article(index):

    put(index, "es", "Las renovables superan al carbón", language="es", seed=1)
    put(index, "en", "Renewables are cheaper", language="en", topic="space", seed=2)

    results = MapSearch(index).search("renovables carbon", "c", semantic=False)["results"]

    assert [r["title"] for r in results if r["kind"] == "article"] == ["Las renovables superan al carbón"]
    assert results[0]["reason"] == "in the title"


def test_a_spanish_topic_stem_finds_the_topics_articles(index):

    put(index, "school", "A new term begins", topic="education", seed=1)
    put(index, "space", "A rocket launches", topic="space", seed=2)

    results = MapSearch(index).search("escuelas", "c", semantic=False)["results"]

    assert [r["title"] for r in results] == ["A new term begins"]
    assert results[0]["reason"] == f"about {TOPICS['education'].name}"


def test_meaning_finds_an_article_with_no_word_in_common(index):

    put(index, "one", "Wetland restored by volunteers", seed=7)
    put(index, "two", "A rocket launches", topic="space", seed=8)

    target = np.asarray(unit(7))
    search = MapSearch(index, embed=lambda text: target)

    answer = search.search("bringing marshes back", "c")

    assert answer["semantic"] == "used"
    assert [r["title"] for r in answer["results"]] == ["Wetland restored by volunteers"]
    assert answer["results"][0]["reason"].startswith("close in meaning")


def test_with_inference_down_it_still_answers_by_name_and_word(index):

    put(index, "one", "Wetland restored by volunteers", seed=7)

    def down(text):
        raise InferenceUnavailable("timed out")

    answer = MapSearch(index, embed=down).search("wetland", "c")

    assert answer["semantic"] == "unavailable"
    assert [r["title"] for r in answer["results"]] == ["Wetland restored by volunteers"]


def test_no_unpublished_article_is_ever_returned(index):

    put(index, "pub", "Wetland restored by volunteers", seed=7)
    put(index, "rej", "Wetland drained for a car park", seed=8, validation_passed=False)

    everything = np.asarray(unit(8))
    answer = MapSearch(index, embed=lambda text: everything).search("wetland", "c")

    assert [r["title"] for r in answer["results"]] == ["Wetland restored by volunteers"]


def test_the_31st_search_in_a_minute_is_refused_and_says_when_to_retry(index):

    clock = Clock()
    search = MapSearch(index, embed=lambda text: np.asarray(unit(1)), clock=clock)

    for _ in range(SEMANTIC_PER_MINUTE):
        search.search("anything", "one-visitor")

    with pytest.raises(RateLimited) as refused:
        search.search("anything", "one-visitor")

    assert 1 <= refused.value.retry_after <= 60
    # Another visitor is not affected, and a minute later this one is not either.
    search.search("anything", "another-visitor")
    clock.now += 61
    search.search("anything", "one-visitor")


def test_type_ahead_has_its_own_looser_limit():

    clock = Clock()
    limiter = RateLimiter(3, clock=clock)

    for _ in range(3):
        limiter.check("x")

    with pytest.raises(RateLimited):
        limiter.check("x")


def test_a_repeated_search_is_answered_from_the_cache_until_the_map_changes(index):

    put(index, "one", "Wetland restored by volunteers", seed=7)

    calls = []
    search = MapSearch(index, embed=lambda text: calls.append(text) or np.asarray(unit(7)))

    search.search("Wetland", "c")
    search.search("wetland ", "c")
    assert len(calls) == 1

    put(index, "two", "Another wetland", seed=9)
    assert len(search.search("wetland", "c")["results"]) == 2
    assert len(calls) == 2


def test_a_query_past_the_cap_is_refused(index):

    with pytest.raises(ValueError):
        MapSearch(index).search("x" * (MAX_QUERY + 1), "c")
