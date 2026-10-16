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
    EMBEDDING_BATCH_SIZE: int = 1


settings = Settings()
