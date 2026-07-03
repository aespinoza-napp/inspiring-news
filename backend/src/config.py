from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    STORAGE_PATH: Path = Path("data/news")

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr


settings = Settings()

settings.STORAGE_PATH.mkdir(
    parents=True,
    exist_ok=True,
)