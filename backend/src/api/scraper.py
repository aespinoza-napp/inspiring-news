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