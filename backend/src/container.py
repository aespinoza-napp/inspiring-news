from src.database.local_repository import LocalRepository
from src.config import settings


repository = LocalRepository(
    settings.STORAGE_PATH
)