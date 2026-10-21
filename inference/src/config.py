from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Deliberately small next to backend/src/config/settings.py - this
    service has no thresholds, no storage paths, no per-run tunables.
    It is a model server: what it needs to know is which weights to
    load and where to listen.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    HOST: str = "0.0.0.0"
    PORT: int = 8001

    GLINER_MODEL: str = "urchade/gliner_small-v2.1"

    # Same model/dimension pairing as backend/.env - kept independently
    # configurable here (rather than shared code) since the two services
    # ship separately and this one owns the model, not the config that
    # decides which threshold gates on it.
    SENTIMENT_MODEL: str = "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # How many texts bge-m3 encodes per forward pass inside one request.
    # On a CPU, one at a time is fastest. Measured 2026-10-16 on the dev
    # laptop (i7-12700H), the ranker's own request - eight evidence pages
    # cut at 2,000 characters - took 9.4 s as one batch and 6.6 s one by
    # one; with the lengths it really sends (some pages are only a
    # snippet) 7.3 s against 4.0 s, because a batch pads every text to
    # the longest. Vectors identical to 3e-7. sentence-transformers'
    # default is 32, which is right for a GPU: raise it there.
    #
    # But one at a time is slowest for *short* texts, which pad nothing:
    # the 163 topic keywords (TopicClassifier, once per backend process,
    # in the first article analysed) took 17.9 s one by one and 4.5 s in
    # batches; a claim's 21 search snippets (the retriever's funnel) 12.6 s
    # and 6.5 s; eight pages and three snippets 16.7 s and 16.9 s. Measured
    # 2026-10-21 on the dev laptop (Core Ultra 7 165U), vectors equal to
    # 2e-7 (docs/decisions/performance.md). So texts are sorted by length
    # and batched while a batch, padded to its longest, stays within this
    # many tokens: short texts go together, a long page goes alone. 0 is
    # one at a time, as before. EMBEDDING_BATCH_SIZE caps the texts per batch.
    EMBEDDING_BATCH_TOKENS: int = 2048
    EMBEDDING_BATCH_SIZE: int = 64


settings = Settings()
