# builders/source_builder.py

from src.models.source import NewsSource


def build_source(**kwargs):

    defaults = {
        "name": "BBC",
        "url": "https://bbc.com",
        "rss_url": "https://bbc.com/rss.xml",
    }

    defaults.update(kwargs)

    return NewsSource(**defaults)