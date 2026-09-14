"""
EMBEDDING_DIMENSION and the model actually running in inference/ are two
independently-set values - nothing enforces that they agree, and
VectorRepository sizes the Qdrant collection from EMBEDDING_DIMENSION
alone, not from the model's real output. This is the same drift risk
tests/processors/nlp/test_embeddings.py's real-model version guarded
before the ML split; the check itself moved here because agreement can
now only be verified against a real, reachable inference service - the
fake/stub used in tests/processors/nlp/test_embeddings.py can't assert
anything about what the real model actually outputs.

Skips rather than fails when inference isn't reachable, same as
test_connection.py does for Neo4j - see conftest.py's require_inference.
"""

from src.config.settings import settings
from src.services.embeddings.service import EmbeddingService


def test_embedding_service_dimension_matches_configured_dimension(require_inference):

    assert EmbeddingService().dimension == settings.EMBEDDING_DIMENSION
