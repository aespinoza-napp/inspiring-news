"""
The last discovery step: a source's topic section pages, read as HTML.

The first two steps both need a feed. Four of the twelve configured feed
URLs went 404 (National Geographic, Reuters, RTVE, SINC) and their
homepages advertise no feed trafilatura can find - so those sources
produced nothing at all, although their sites were up and full of
articles. Every news site files its articles under sections, and the
sections this project cares about are exactly the ones TOPIC_URL_PATTERNS
already names (/science/, /health/, /environment/...). This step reads
those section pages and keeps the article links on them.

Which sections, in order:

1. The ones the homepage links to - they exist, so no request is wasted
   on a guess. One request for the homepage.
2. Then `base_url + pattern` guesses, one per topic, for sites that do
   not link their sections from the homepage. A guess that 404s costs a
   request, which is why the total is capped (`max_sections`) - and why
   there are none when the homepage itself was refused.

Spanish sources also get TOPIC_SECTION_PATTERNS_ES: El País files science
under /ciencia/, and guessing /science/ there only buys a 404.

Every fetch goes through Fetcher, so the URL guard and the timeout apply;
the article URLs found are guarded again when they are extracted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup

from src.config.topic_url_patterns import TOPIC_SECTION_PATTERNS_ES, TOPIC_URL_PATTERNS
from src.config.topics import GROUP_OF
from src.models.core.source import NewsSource
from src.services.scraper.fetcher import Fetcher, classify

from .rss import DiscoveredLink, RSSDiscoveryStrategy, article_shaped, off_mission


# A link's text is its headline when it has at least this many words
# ("Leer más", "Ciencia", "9 oct 2026" are not), cut to HEADLINE_CHARS.
HEADLINE_WORDS = 4
HEADLINE_CHARS = 300

# RTVE labels each link with its kind: "Noticia: Así se hace el auténtico
# bacalao de Valderas". Not part of the headline.
CONTENT_LABEL = re.compile(r"^(?:Noticia|Noticias|News)\s*:\s*", re.IGNORECASE)

# A section page is a short path: /science/, /news/science/,
# /es/ciencia/. Anything deeper is an article or a sub-sub-section.
MAX_SECTION_DEPTH = 3


@dataclass
class SectionPage:
    """One section page tried, and what came of it."""

    url: str

    # Linked from the homepage (True), or guessed from the base URL.
    advertised: bool

    status: int | None = None

    # An Outcome value: ok, http_error, timeout, ...; "ok" with no links
    # means the page came back and carried no article links.
    outcome: str = "ok"

    error: str | None = None

    links: list[str] = field(default_factory=list)

    # link -> the headline the page links it with (see _anchors).
    titles: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:

        return {
            "url": self.url,
            "advertised": self.advertised,
            "status": self.status,
            "outcome": self.outcome,
            "error": self.error,
            "links": len(self.links),
        }


@dataclass
class TopicPagesResult:

    homepage_status: int | None = None

    homepage_outcome: str = "ok"

    homepage_error: str | None = None

    sections: list[SectionPage] = field(default_factory=list)

    @property
    def urls(self) -> list[str]:

        return list(dict.fromkeys(
            link for section in self.sections for link in section.links
        ))

    @property
    def titles(self) -> dict[str, str]:

        titles: dict[str, str] = {}

        for section in self.sections:
            for link, title in section.titles.items():
                titles.setdefault(link, title)

        return titles


class TopicPageDiscoveryStrategy(RSSDiscoveryStrategy):

    def __init__(self, fetcher: Fetcher | None = None, max_sections: int = 6):

        super().__init__(fetcher)

        self.max_sections = max_sections

    def discover(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[str]:

        return self.crawl(source, topics).urls

    def discover_items(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> list[DiscoveredLink]:
        """
        The section pages' article links, each titled with the headline the
        page links it with - no feed time or summary: there is no feed.
        Overridden because DiscoveryService asks for items, and the one
        inherited from RSSDiscoveryStrategy reads the feed: from 2026-10-04
        (when discovery started asking for feed times) to 2026-10-05 this
        step re-read the dead feed of every source it exists for instead of
        crawling a single section.
        """

        result = self.crawl(source, topics)
        titles = result.titles

        return [DiscoveredLink(url=url, title=titles.get(url)) for url in result.urls]

    def crawl(
        self,
        source: NewsSource,
        topics: list[str] = None,
    ) -> TopicPagesResult:
        """`discover`, with what happened on every page - for the probe."""

        result = TopicPagesResult()

        base = str(source.base_url)
        patterns = self._section_patterns(source, topics)

        advertised: list[str] = []

        try:
            homepage = self.fetcher.get(base)
            result.homepage_status = homepage.status
            advertised = self._advertised_sections(base, homepage.html, patterns)
        except Exception as exc:
            outcome, status, error = classify(exc)
            result.homepage_outcome = outcome.value
            result.homepage_status = status
            result.homepage_error = error

        # A site that refused its own homepage (EFE 403, Reuters 401 in the
        # 2026-09-25 probe) refuses its sections the same way: six guesses
        # there were six more refusals and nothing else.
        guessed = [] if result.homepage_error else [
            urljoin(base, pattern.lstrip("/")) for pattern in self._first_per_topic(source, topics)
        ]

        candidates = [(url, True) for url in advertised] + [(url, False) for url in guessed]

        seen: set[str] = set()

        for url, is_advertised in candidates:

            key = _normalised(url)

            if key in seen:
                continue

            seen.add(key)

            if len(result.sections) >= self.max_sections:
                break

            result.sections.append(self._read_section(source, url, is_advertised, patterns))

        return result

    ##########################################################

    def _read_section(
        self,
        source: NewsSource,
        url: str,
        advertised: bool,
        patterns: list[str],
    ) -> SectionPage:

        section = SectionPage(url=url, advertised=advertised)

        try:
            page = self.fetcher.get(url)
        except Exception as exc:
            outcome, status, error = classify(exc)
            section.outcome = outcome.value
            section.status = status
            section.error = error
            return section

        section.status = page.status

        links = []
        headlines: dict[str, str] = {}

        for link, text in _anchors(page.url, page.html):

            # The longest readable text a link carries on the page: a
            # teaser's image link has none, its headline link has it.
            text = CONTENT_LABEL.sub("", text)
            if _headline(text) and len(text) > len(headlines.get(link, "")):
                headlines[link] = text[:HEADLINE_CHARS]

            if not _same_site(link, str(source.base_url)):
                continue

            # A section page links to its siblings; /science/ matches the
            # article-shape patterns, so it has to be ruled out here.
            if _is_section_path(urlsplit(link).path, patterns):
                continue

            if _normalised(link) == _normalised(url):
                continue

            # By its own shape, not its section (article_shaped); and a
            # science section's sidebar still links the match reports.
            if article_shaped(link) and not off_mission(link):
                links.append(link)

        section.links = _within_section(list(dict.fromkeys(links)), page.url)
        section.titles = {link: headlines[link] for link in section.links if link in headlines}

        if not section.links:
            section.error = "no article links on the page"

        return section

    @staticmethod
    def _advertised_sections(base: str, html: str, patterns: list[str]) -> list[str]:

        found = []

        for link in _links(base, html):

            if _same_site(link, base) and _is_section_path(urlsplit(link).path, patterns):
                found.append(link)

        return list(dict.fromkeys(found))

    @staticmethod
    def _section_patterns(source: NewsSource, topics: list[str] | None) -> list[str]:

        configured = _configured_sections(source, topics)

        if configured:
            return configured

        wanted = _wanted_topics(topics)

        tables = [TOPIC_URL_PATTERNS]

        if (source.language or "en").lower().startswith("es"):
            tables.insert(0, TOPIC_SECTION_PATTERNS_ES)

        return list(dict.fromkeys(
            pattern
            for table in tables
            for topic, patterns in table.items()
            if wanted is None or topic in wanted
            for pattern in patterns
        ))

    @staticmethod
    def _first_per_topic(source: NewsSource, topics: list[str] | None) -> list[str]:
        """One guess per topic - the name the site is likeliest to use - or the sections the source names."""

        configured = _configured_sections(source, topics)

        if configured:
            return configured

        wanted = _wanted_topics(topics)

        table = (
            TOPIC_SECTION_PATTERNS_ES
            if (source.language or "en").lower().startswith("es")
            else TOPIC_URL_PATTERNS
        )

        return list(dict.fromkeys(
            patterns[0]
            for topic, patterns in table.items()
            if (wanted is None or topic in wanted) and patterns
        ))


def _configured_sections(source: NewsSource, topics: list[str] | None) -> list[str]:
    """The section paths `source` names for the groups of `topics` (every group when None); [] when it names none."""

    wanted = _wanted_topics(topics)
    groups = {GROUP_OF[topic] for topic in wanted if topic in GROUP_OF} if wanted is not None else set(source.sections)

    return list(dict.fromkeys(
        path for group, paths in source.sections.items() if group in groups for path in paths
    ))


def _within_section(links: list[str], section_url: str) -> list[str]:
    """
    A section page's own articles, when it files them under its path:
    ABC's /cultura/ page also links the day's top stories, and on
    2026-10-06 two election pieces under /espana/ came back as Culture
    candidates. A site whose article URLs carry no section (SINC's
    /Noticias/...) keeps every link, as before - there is nothing to
    tell them apart by.
    """

    prefix = "/" + urlsplit(section_url).path.strip("/").lower() + "/"

    own = [link for link in links if urlsplit(link).path.lower().startswith(prefix)]

    return own or links


def _wanted_topics(topics: list[str] | None) -> set[str] | None:

    if not topics:
        return None

    return {topic.lower().strip() for topic in topics}


def _links(page_url: str, html: str) -> list[str]:

    return [link for link, _ in _anchors(page_url, html)]


def _anchors(page_url: str, html: str) -> list[tuple[str, str]]:
    """
    Every absolute http(s) link on the page, with the text it is linked
    with (its own text, else its aria-label or title attribute). A section
    page's links come with their headlines: until 2026-10-09 they were
    dropped and the candidate was titled from its slug ("Aniversario bizum
    cambio nuestra forma pagar cumple anos"), and the mission screen, the
    ranking and the same-story check all read that.
    """

    soup = BeautifulSoup(html or "", "html.parser")

    anchors = []

    for anchor in soup.find_all("a", href=True):

        href = anchor["href"].strip()

        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue

        absolute, _ = urldefrag(urljoin(page_url, href))

        if absolute.lower().startswith(("http://", "https://")):
            text = " ".join(anchor.get_text(" ", strip=True).split())
            text = text or (anchor.get("aria-label") or anchor.get("title") or "").strip()
            anchors.append((absolute, text))

    return anchors


def _headline(text: str) -> bool:
    """Text that reads as a headline: a few words, not "Read more" or a date."""

    return len(text.split()) >= HEADLINE_WORDS


def _host(url: str) -> str:

    return urlsplit(url).netloc.lower().removeprefix("www.")


def _same_site(link: str, base: str) -> bool:
    """The source's own host or a subdomain of it - not an ad or a partner."""

    host, root = _host(link), _host(base)

    return bool(host) and (host == root or host.endswith("." + root) or root.endswith("." + host))


def _is_section_path(path: str, patterns: list[str]) -> bool:

    path = "/" + path.strip("/").lower() + "/"

    depth = len([part for part in path.split("/") if part])

    return 0 < depth <= MAX_SECTION_DEPTH and any(path.endswith(pattern) for pattern in patterns)


def _normalised(url: str) -> str:

    parts = urlsplit(url)

    return f"{_host(url)}{parts.path.rstrip('/')}".lower()
