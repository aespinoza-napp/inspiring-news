from neo4j import GraphDatabase

class GraphClient:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def verify_connection(self):
        return self.driver.verify_connectivity()

    async def save_news_node(self, article):
        with self.driver.session() as session:
            session.run("""
                MERGE (a:Article {url: $url})
                SET a.title = $title, a.sentiment = $sentiment, a.status = $status
                WITH a
                UNWIND $keywords AS kw
                MERGE (k:Keyword {name: kw})
                MERGE (a)-[:HAS_KEYWORD]->(k)
            """, url=article.url, title=article.title, 
                 sentiment=article.sentiment_score, 
                 status=article.fact_check_status,
                 keywords=article.keywords)