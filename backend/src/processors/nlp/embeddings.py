from src.services.embeddings.service import EmbeddingService

from .base import BaseProcessor


class EmbeddingProcessor(BaseProcessor):

    def __init__(self):

        self.service = EmbeddingService()

    def process(self, text: str):

        return self.service.encode(text)