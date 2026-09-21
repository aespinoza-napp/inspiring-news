from pydantic import BaseModel, Field


class TopicKeyword(BaseModel):
    """
    One of a topic's own defining keywords (src/config/topics.py), scored
    against this specific article.
    """

    keyword: str

    # Cosine similarity between the keyword and the whole article. Raw
    # values are small and close together (word vs. document); only their
    # order and relative size mean anything.
    score: float

    # How many times the keyword appears in the text, literally. Zero is
    # common and not an error: the lists are English, so a Spanish article
    # scores on meaning while mentioning few of them verbatim.
    mentions: int = 0


class TopicPrediction(BaseModel):
    topic: str
    confidence: float
    probability: float

    # The topic's keywords, closest to the article first.
    keywords: list[TopicKeyword] = Field(default_factory=list)
