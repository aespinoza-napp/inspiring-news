from typing import Optional

from src.models.news import News
from src.models.source import NewsSource


class Scraper:
    """
    Generic article scraper.

    Given a source and a URL, it tries different extraction strategies
    until one succeeds.
    """

    def scrape(
        self,
        source: NewsSource,
        url: str,
    ) -> Optional[News]:

        article = self._try_rss(source, url)

        if article:
            return article

        article = self._try_trafilatura(source, url)

        if article:
            return article

        article = self._try_newspaper(source, url)

        if article:
            return article

        article = self._try_beautifulsoup(source, url)

        return article

    def _try_rss(self, source, url):
        return None

    def _try_trafilatura(self, source, url):
        return None

    def _try_newspaper(self, source, url):
        return None

    def _try_beautifulsoup(self, source, url):
        return None