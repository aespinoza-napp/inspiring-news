from pydantic import BaseModel


class DuplicateResult(BaseModel):

    duplicate: bool

    similarity: float

    matched_article_id: str | None = None

    reason: str | None = None