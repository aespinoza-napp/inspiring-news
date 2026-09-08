from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    STORAGE_PATH: Path = Path("data")

    RAW_PATH: Path = STORAGE_PATH / "raw"

    PROCESSED_PATH: Path = STORAGE_PATH / "processed"

    EMBEDDINGS_PATH: Path = STORAGE_PATH / "embeddings"

    FACT_CHECK_PATH: Path = STORAGE_PATH / "fact_checks"

    GRAPH_PATH: Path = STORAGE_PATH / "graph"

    CACHE_PATH: Path = STORAGE_PATH / "cache"

    # Three-layer storage lake (raw -> processed -> exploitation).
    # Deliberately *not* the legacy RAW_PATH/PROCESSED_PATH scratch
    # directories above: those hold bare News/EnrichedArticle JSON
    # written ad hoc by scripts and tests, while the lake holds
    # lineage-stamped records and must not be mixed with them.
    LAKE_PATH: Path = STORAGE_PATH / "lake"

    # Whether the pipeline writes to the lake at all. Off makes
    # AnalysisService pure (no side effects) for tests/dry runs.
    LAKE_ENABLED: bool = True

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr

    # Multilingual (covers the en/es/... mix of currently configured
    # sources) - twitter-roberta-base-sentiment-latest is English-only and
    # would silently produce meaningless scores for non-English articles.
    SENTIMENT_MODEL: str = (
        "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    )

    # Qdrant settings
    QDRANT_PATH: Path = Path("data/vector_db")

    EMBEDDING_DIMENSION: int = 1024

    EMBEDDING_MODEL: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # -----------------------------------------------------------------
    # Pipeline thresholds
    #
    # These are the *defaults*. A single run can override any of them
    # per request (see src/config/thresholds.py and the `thresholds`
    # field on POST /analyze and POST /analyze/jobs); anything the
    # caller leaves out falls back to the value below.
    #
    # Read them through a PipelineThresholds instance, never as a class
    # attribute evaluated at import time - `MIN_X = settings.MIN_X` in a
    # class body freezes the value when the module is first imported,
    # which is why per-run overrides (and even plain env changes under
    # some import orders) had no effect before.
    # -----------------------------------------------------------------

    # Enrichment
    TOPIC_CLASSIFIER_THRESHOLD: float = 0.35
    ENTITY_THRESHOLD: float = 0.50
    CLAIM_MIN_CONFIDENCE: float = 0.50

    # Extraction: shortest body accepted as a real article, in characters
    MIN_BODY_LENGTH: int = 500

    # Admission filter
    TOPIC_MIN_CONFIDENCE: float = 0.35
    POSITIVE_IMPACT_MIN_SCORE: float = 0.30

    # Similarity threshold for duplicate detection
    DUPLICATE_THRESHOLD: float = 0.90
    RELATEDNESS_THRESHOLD: float = 0.80

    # SearXNG (self-hosted meta-search, used for fact-check evidence retrieval)
    SEARXNG_URL: str = "http://localhost:8080"
    SEARXNG_TIMEOUT: float = 10.0
    SEARXNG_MAX_RESULTS: int = 8

    # LLM (OpenAI-compatible chat completions; defaults to a local Ollama
    # instance so verification is free/open-source by default. Swapping to
    # Groq/OpenRouter/Together/real OpenAI is a settings-only change.
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: SecretStr = SecretStr("ollama")
    LLM_MODEL: str = "llama3.1"
    LLM_TIMEOUT: float = 60.0

    # Claim selection
    MAX_CLAIMS_PER_ARTICLE: int = 5
    CLAIM_DEDUP_THRESHOLD: float = 0.92

    # Evidence retrieval / ranking
    EVIDENCE_FETCH_CANDIDATES: int = 8
    MAX_EVIDENCE_PER_CLAIM: int = 5
    EVIDENCE_RECENCY_HALF_LIFE_DAYS: float = 365.0
    MIN_EVIDENCE_FOR_VERDICT: int = 1

    # EvidenceRanker scoring weights (must sum to 1.0)
    RANKING_SEMANTIC_WEIGHT: float = 0.60
    RANKING_RECENCY_WEIGHT: float = 0.25
    RANKING_RELIABILITY_WEIGHT: float = 0.15
    RANKING_DEFAULT_RELIABILITY: float = 0.5

    # ConfidenceScorer weights (must sum to 1.0)
    CONFIDENCE_LLM_WEIGHT: float = 0.7
    CONFIDENCE_EVIDENCE_WEIGHT: float = 0.3


settings = Settings()

for folder in (
    settings.STORAGE_PATH,
    settings.RAW_PATH,
    settings.PROCESSED_PATH,
    settings.EMBEDDINGS_PATH,
    settings.FACT_CHECK_PATH,
    settings.GRAPH_PATH,
    settings.CACHE_PATH,
    settings.LAKE_PATH,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )