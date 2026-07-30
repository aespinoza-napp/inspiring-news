
from pydantic import BaseModel


class DuplicateResult(BaseModel):

    duplicate: bool

    duplicate_article_id: str | None

    similarity: float