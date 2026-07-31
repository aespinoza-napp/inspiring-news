from pydantic import BaseModel


class TopicPrediction(BaseModel):
    topic: str
    confidence: float
    probability: float