from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    STORAGE_PATH: Path = Path("data/news")

    # Database settings
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr

    # Sentiment analysis settings
    SENTIMENT_MODEL: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"


settings = Settings()

settings.STORAGE_PATH.mkdir(
    parents=True,
    exist_ok=True,
)