from src.models.scraper.extraction import ExtractionResult


class ExtractionValidator:

    MIN_BODY_LENGTH = 500

    @classmethod
    def is_valid(
        cls,
        article: ExtractionResult,
    ) -> bool:

        #if not article.title:
        #    return False

        if len(article.body.strip()) < cls.MIN_BODY_LENGTH:
            return False

        return True