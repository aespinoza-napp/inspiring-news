from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):

    STORAGE_PATH: Path = Path("data/news")

    class Config:
        env_file = ".env"


settings = Settings()

settings.STORAGE_PATH.mkdir(
    parents=True,
    exist_ok=True,
)