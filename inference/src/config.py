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


settings = Settings()
