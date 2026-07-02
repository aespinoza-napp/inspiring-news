import json
from pathlib import Path

from src.models.news import News

from .repository import NewsRepository


class LocalRepository(NewsRepository):

    def __init__(self, folder: Path):

        self.folder = folder

        self.folder.mkdir(
            exist_ok=True,
            parents=True,
        )

    def _filename(
        self,
        news: News,
    ):

        date = news.published_at.date()

        return (
            self.folder /
            f"{news.source}_{date}_{news.id}.json"
        )

    def save(
        self,
        news: News,
    ):

        file = self._filename(news)

        file.write_text(
            news.model_dump_json(indent=4)
        )

    def load(
        self,
        news_id: str,
    ):

        for file in self.folder.glob("*.json"):

            if news_id in file.name:

                return News.model_validate_json(
                    file.read_text()
                )

        raise FileNotFoundError(news_id)

    def list(self):

        return [

            News.model_validate_json(
                file.read_text()
            )

            for file in self.folder.glob("*.json")

        ]