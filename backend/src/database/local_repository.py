from pathlib import Path

from logging import getLogger

from src.config.settings import settings
from src.models.news import News

from .repository import NewsRepository

logger = getLogger(__name__)

class LocalRepository(NewsRepository):

    def __init__(
        self,
        folder: Path | None = None,
    ):

        self.folder = folder or settings.STORAGE_PATH

        self.folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    ####################################################

    def __iter__(self):

        yield from self.list()

    ####################################################

    def _filename(
        self,
        news: News,
    ) -> Path:

        date = news.published_at.date()

        return (
            self.folder
            / f"{date}_{news.source_id}_{news.id}.json"
        )

    ####################################################

    def save(
        self,
        news: News,
    ):

        self._filename(news).write_text(
            news.model_dump_json(indent=2),
            encoding="utf-8",
        )

    ####################################################

    def load(
        self,
        news_id: str,
    ) -> News:

        for file in self.folder.glob("*.json"):

            if news_id in file.name:

                return News.model_validate_json(
                    file.read_text()
                )

        raise FileNotFoundError(news_id)

    ####################################################

    def list(self) -> list[News]:

        articles = []

        for file in self.folder.glob("*.json"):

            try:

                article = News.model_validate_json(
                    file.read_text(
                        encoding="utf-8",
                    )
                )

                articles.append(article)

            except Exception as e:

                logger.warning(
                    "Cannot read %s: %s",
                    file,
                    e,
                )

        return sorted(
            articles,
            key=lambda news: news.published_at,
            reverse=True,
        )

    ####################################################

    def first(self) -> News | None:

        articles = self.list()

        return articles[0] if articles else None