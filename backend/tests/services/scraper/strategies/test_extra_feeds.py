"""
A source's extra feeds (2026-11-10): BBC Future on bbc.com, read with the
news feed by the one BBC source, since one domain is one source.
"""

from types import SimpleNamespace

from src.repositories.source_repository import SourceRepository
from src.services.scraper.strategies.rss import RSSDiscoveryStrategy, _interleaved

from tests.builders.source_builder import build_source


def feed(*slugs: str, host: str = "https://www.bbc.com") -> str:

    items = "".join(
        f"<item><title>Story {slug}</title><link>{host}/{slug}</link></item>" for slug in slugs
    )

    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>'


class Feeds:
    """A fetcher answering each feed URL with its canned XML, or raising."""

    def __init__(self, by_url: dict):

        self.by_url = by_url
        self.asked: list[str] = []

    def get(self, url):

        self.asked.append(url)
        answer = self.by_url[url]

        if isinstance(answer, Exception):
            raise answer

        return SimpleNamespace(html=answer)


NEWS = "https://feeds.example.org/news.xml"
FUTURE = "https://www.bbc.com/future/feed.rss"


def bbc(**extra):

    return build_source(id="bbc", name="BBC", base_url="https://www.bbc.com", rss_url=NEWS, **extra)


def test_without_extra_feeds_only_the_feed_is_read():

    fetcher = Feeds({NEWS: feed("news/a")})

    entries = RSSDiscoveryStrategy(fetcher=fetcher)._entries(bbc())

    assert [entry.link for entry in entries] == ["https://www.bbc.com/news/a"]
    assert fetcher.asked == [NEWS]


def test_extra_feeds_are_read_and_interleaved_so_neither_crowds_out_the_other():

    fetcher = Feeds({NEWS: feed("news/a", "news/b", "news/c"), FUTURE: feed("future/x")})

    entries = RSSDiscoveryStrategy(fetcher=fetcher)._entries(bbc(extra_feeds=[FUTURE]))

    assert [entry.link.removeprefix("https://www.bbc.com/") for entry in entries] == [
        "news/a", "future/x", "news/b", "news/c",
    ]


def test_a_failing_extra_feed_costs_only_its_own_items():

    fetcher = Feeds({NEWS: feed("news/a"), FUTURE: TimeoutError("timed out")})

    entries = RSSDiscoveryStrategy(fetcher=fetcher)._entries(bbc(extra_feeds=[FUTURE]))

    assert [entry.link for entry in entries] == ["https://www.bbc.com/news/a"]


def test_interleaving_keeps_every_item_once():

    assert _interleaved([[1, 2, 3], [], [10, 20]]) == [1, 10, 2, 20, 3]
    assert _interleaved([]) == []


def test_bbc_reads_bbc_future():

    assert FUTURE in [str(url) for url in SourceRepository().get("bbc").extra_feeds]
