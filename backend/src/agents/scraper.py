from datetime import datetime

from src.models.news import News


class ScraperAgent:

    def fetch_latest(self):

        return [

            News(
                title="NASA discovers water on Mars",
                source="cnn",
                url="https://cnn.com/news/1",
                published_at=datetime.now(),
                content=(
                    "NASA discovered water on Mars. "
                    "Scientists confirmed the discovery. "
                    "A fake image circulated online."
                ),
            ),

            News(
                title="OpenAI releases GPT-X",
                source="reuters",
                url="https://reuters.com/news/2",
                published_at=datetime.now(),
                content=(
                    "OpenAI announced GPT-X. "
                    "Developers welcomed the release."
                ),
            ),
        ]

"""
import requests
from bs4 import BeautifulSoup

class ScraperAgent:
    def fetch_article(self, url: str):
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Basic extraction: Title and first few paragraphs
        title = soup.find('h1').text if soup.find('h1') else "No Title"
        paragraphs = soup.find_all('p')
        content = " ".join([p.text for p in paragraphs[:3]])
        
        return {"title": title, "content": content, "url": url}


"""