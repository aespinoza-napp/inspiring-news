"""
Every source names the topic groups it is read for, and every group can
be read in both languages - so picking any group (POST /ingest/rounds)
never returns an English-only or Spanish-only list.
"""

import pytest

from src.config.topics import TOPIC_GROUPS
from src.models.core.source import NewsSource
from src.repositories.source_repository import SourceRepository


def sources() -> list[NewsSource]:

    return SourceRepository("data/sources").list()


def test_every_enabled_source_names_at_least_one_group():

    missing = [source.id for source in sources() if source.enabled and not source.groups]

    assert missing == []


@pytest.mark.parametrize("group", list(TOPIC_GROUPS))
def test_every_group_has_an_english_and_a_spanish_source(group):

    languages = {source.language for source in sources() if source.enabled and group in source.groups}

    assert {"en", "es"} <= languages


def test_only_the_outlets_that_publish_nothing_but_positive_news_skip_the_mission_screen():
    """A general outlet marked positive would let its election coverage through unscreened."""

    exempt = sorted(source.id for source in sources() if source.positive_editorial)

    assert exempt == ["good_news_network", "positive_news", "reasons_to_be_cheerful"]


def test_an_unknown_group_is_refused_when_the_yaml_is_read():

    with pytest.raises(ValueError, match="unknown topic group"):
        NewsSource(id="x", name="X", base_url="https://x.example", groups=["sports"])
