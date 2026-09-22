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

    # Documentary, not load-bearing: the model itself now loads inside
    # inference/ (inference/src/config.py's own SENTIMENT_MODEL), not
    # here. Kept so a human reading .env still sees what's running.
    # Changing this value does NOT change behavior - change
    # inference/src/config.py's default (or that service's own env) and
    # rebuild/restart it instead.
    SENTIMENT_MODEL: str = (
        "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    )

    # Qdrant settings
    QDRANT_PATH: Path = Path("data/vector_db")

    # Still load-bearing: VectorRepository sizes the Qdrant collection
    # from this, independent of which embedding model actually produces
    # the vectors (see backend/tests/services/test_embeddings.py's
    # config-drift test for why the two must actually agree).
    EMBEDDING_DIMENSION: int = 1024

    # Documentary only, same caveat as SENTIMENT_MODEL above - the model
    # loads in inference/src/config.py now.
    EMBEDDING_MODEL: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # The model server for GLiNER/sentiment/embeddings (inference/) -
    # see backend/src/services/inference_client.py. Defaults to
    # localhost for running both services on the host during local dev,
    # same pattern as LLM_BASE_URL below; docker-compose.yml overrides
    # this to the container DNS name.
    INFERENCE_URL: str = "http://localhost:8001"
    INFERENCE_TIMEOUT: float = 30.0

    # How many /analyze/jobs runs (single or batch) may execute at once.
    # A process resource limit, not a per-run pipeline threshold - each
    # run still does real scraping, inference/ HTTP calls, a SearXNG
    # search and an LLM call, so unbounded concurrency here is what
    # overloads those, not the pipeline logic itself. See
    # src/services/job_queue.py.
    ANALYSIS_MAX_CONCURRENCY: int = 3

    # -----------------------------------------------------------------
    # Fan-out and resource ceilings (see src/services/concurrency.py)
    #
    # Fact-checking runs claims concurrently, and each claim runs its two
    # searches and its page fetches concurrently too. Those multiply -
    # ANALYSIS_MAX_CONCURRENCY x CLAIM_MAX_CONCURRENCY x
    # SCRAPE_MAX_CONCURRENCY is the worst case - so the fan-out numbers
    # are chosen for what is sensible to watch at once and the real
    # ceiling is the per-resource limit below, applied once per process.
    #
    # Infrastructure, not per-run tunables: a request must not be able to
    # raise how hard this process hits a service every other request
    # shares. Same reasoning as ANALYSIS_MAX_CONCURRENCY above.
    # -----------------------------------------------------------------

    # How many of an article's claims are verified at the same time.
    CLAIM_MAX_CONCURRENCY: int = 4

    # How many of one claim's queries are sent at the same time. Two is
    # the whole set today (affirmative + refutation).
    QUERY_MAX_CONCURRENCY: int = 2

    # Zero or below means unbounded, for tests and single-user local runs.
    SEARXNG_MAX_CONCURRENCY: int = 4
    SCRAPE_MAX_CONCURRENCY: int = 8
    INFERENCE_MAX_CONCURRENCY: int = 4
    LLM_MAX_CONCURRENCY: int = 2

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

    # -----------------------------------------------------------------
    # Fetch guard (SSRF)
    #
    # Every fetch is server-side with a URL from outside the process, so
    # without this the service proxies into whatever network it runs on -
    # including the compose network that holds Neo4j and SearXNG, and any
    # cloud metadata endpoint. Off is for offline tests only.
    # -----------------------------------------------------------------
    URL_GUARD_ENABLED: bool = True

    # Hostnames exempt from the private-address check. Empty by default;
    # an escape hatch for a staging host on a private network, so nobody
    # reaches for URL_GUARD_ENABLED=false to solve that.
    URL_GUARD_ALLOWED_HOSTS: list[str] = []

    # When set, /storage/* requires this value in an X-API-Key header.
    # Unset leaves those endpoints open, which is fine on localhost and
    # not fine anywhere else - src/main.py logs a warning at startup so
    # that choice is never silent.
    STORAGE_API_KEY: SecretStr | None = None

    # Enrichment
    TOPIC_CLASSIFIER_THRESHOLD: float = 0.35
    ENTITY_THRESHOLD: float = 0.50
    CLAIM_MIN_CONFIDENCE: float = 0.50

    # Above this, a sentence reads as opinion/interpretation and is not
    # extracted as a claim at all. Deliberately permissive: news prose is
    # full of mild evaluative language, and a low ceiling here throws away
    # checkable sentences that merely sound enthusiastic.
    OPINION_MAX_SCORE: float = 0.50

    # Extraction: shortest body accepted as a real article, in characters
    MIN_BODY_LENGTH: int = 500

    # Admission filter
    TOPIC_MIN_CONFIDENCE: float = 0.35
    POSITIVE_IMPACT_MIN_SCORE: float = 0.1

    # Whether low objectivity / strong negative sentiment reject an
    # article outright, on top of costing it score. See
    # PositiveImpactValidator.validate.
    POSITIVE_IMPACT_HARD_FAIL_ENABLED: bool = False

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
    # llama3.2:3b replaced llama3.1 (8B) as the default: same Ollama/OpenAI
    # wire format, a third of the weights to load alongside inference/'s
    # GLiNER + sentiment + bge-m3, and noticeably faster per-claim
    # verification on a laptop with no GPU. Phase 4 still owns measuring
    # whether it verifies as well - this is a resource swap, not a
    # benchmarked upgrade.
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: SecretStr = SecretStr("ollama")
    LLM_MODEL: str = "llama3.2:3b"
    # Halved from 60s now that the default model is 3B, not 8B - a stuck
    # request still costs at most 2 x this (complete_json's own retry;
    # the SDK's own retries are off, see LLMClient).
    LLM_TIMEOUT: float = 30.0
    # Base delay before complete_json's retry after a connection/timeout
    # failure, doubled each attempt and capped at 5s.
    LLM_RETRY_BACKOFF_SECONDS: float = 0.5

    # Claim selection
    CLAIM_DEDUP_THRESHOLD: float = 0.92

    # The anchor band - how many load-bearing claims actually get verified.
    ANCHOR_CLAIMS_MIN: int = 2
    ANCHOR_CLAIMS_MAX: int = 4

    # Distinct domains needed before a claim counts as corroborated.
    MIN_INDEPENDENT_DOMAINS: int = 2

    # Evidence retrieval / ranking
    EVIDENCE_FETCH_CANDIDATES: int = 8
    MAX_EVIDENCE_PER_CLAIM: int = 5
    EVIDENCE_RECENCY_HALF_LIFE_DAYS: float = 365.0
    MIN_EVIDENCE_FOR_VERDICT: int = 1

    # The pertinence floor: below this, a source is topically related but
    # does not address the assertion, and is cut before the LLM ever sees
    # it. Deliberately low - this is a floor against off-target retrieval,
    # not a relevance ranking, and cutting real evidence here turns a
    # checkable claim into UNVERIFIED.
    EVIDENCE_MIN_PERTINENCE: float = 0.25

    # EvidenceRanker scoring weights (must sum to 1.0)
    #
    # RANKING_LEXICAL_WEIGHT is the newest of the four and the reason the
    # other three moved. Embedding similarity alone ranks a page *about
    # the same subject* as highly as one that addresses the assertion: a
    # claim mentioning ACME retrieved three pages explaining what the word
    # "acme" means in Greek, all at high cosine, and the model cited them
    # as confirmation. Lexical coverage of the claim's own discriminative
    # terms is what those pages have none of.
    RANKING_SEMANTIC_WEIGHT: float = 0.45
    RANKING_LEXICAL_WEIGHT: float = 0.20
    RANKING_RECENCY_WEIGHT: float = 0.20
    RANKING_RELIABILITY_WEIGHT: float = 0.15
    RANKING_DEFAULT_RELIABILITY: float = 0.5

    # How semantic and lexical agreement combine into the single
    # "does this source actually address the claim" figure that the
    # pertinence gate thresholds. Its own normalised pair, kept apart
    # from the ranking weights because it answers a different question:
    # ranking orders sources, pertinence decides whether a source is
    # allowed to support a verdict at all.
    PERTINENCE_SEMANTIC_WEIGHT: float = 0.5
    PERTINENCE_LEXICAL_WEIGHT: float = 0.5

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