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

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr

    SENTIMENT_MODEL: str = (
        "cardiffnlp/twitter-roberta-base-sentiment-latest"
    )

    # Qdrant settings
    QDRANT_PATH: Path = Path("data/vector_db")

    EMBEDDING_DIMENSION: int = 1024

    EMBEDDING_MODEL: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # Similarity threshold for duplicate detection
    DUPLICATE_THRESHOLD: float = 0.90


settings = Settings()

for folder in (
    settings.STORAGE_PATH,
    settings.RAW_PATH,
    settings.PROCESSED_PATH,
    settings.EMBEDDINGS_PATH,
    settings.FACT_CHECK_PATH,
    settings.GRAPH_PATH,
    settings.CACHE_PATH,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )