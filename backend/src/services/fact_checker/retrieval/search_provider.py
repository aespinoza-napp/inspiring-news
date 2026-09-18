import re
from datetime import datetime

from src.config.thresholds import PipelineThresholds
from src.models.core.claim import Claim
from src.models.fact_checker.evidence import Evidence, EvidenceOrigin
from src.services.search import SearxngClient


class SearchProvider:

    # Figures the entity extractor's DEFAULT_LABELS never captures (see
    # src/processors/nlp/entities.py - there is no "date"/"number" label),
    # but which are exactly the kind of detail that pins a claim to one
    # real event ("35%", "2024") rather than a generic one. Cheap enough
    # to pull with a regex here rather than threading claims.py's own
    # NUMBER_PATTERN/YEAR_PATTERN/PERCENT_PATTERN across modules for it.
    # `%` is appended outside the trailing `\b`, not inside it: `%` is not
    # a word character, so a boundary can never follow it when the next
    # character is also non-word (as in "15%.") - the exact bug
    # claims.py's own PERCENT_PATTERN comment documents avoiding.
    FIGURE_PATTERN = re.compile(r"\b\d[\d.,]*\b%?")

    def __init__(self, client: SearxngClient | None = None):

        self.client = client or SearxngClient()

    def search(
        self,
        claim: Claim,
        thresholds: PipelineThresholds | None = None,
    ) -> list[Evidence]:

        thresholds = thresholds or PipelineThresholds()

        raw_results = self.client.search(
            self.build_query(claim),
            max_results=thresholds.evidence_fetch_candidates,
        )

        evidence = []

        for item in raw_results:

            url = item.get("url")
            title = item.get("title")

            if not url or not title:
                continue

            evidence.append(
                Evidence(
                    url=url,
                    title=title,
                    snippet=item.get("content", ""),
                    published_at=self._parse_date(item.get("publishedDate")),
                    origin=EvidenceOrigin.WEB,
                )
            )

        return evidence

    def build_query(self, claim: Claim) -> str:
        """
        Anchors the query on the claim's own named entities instead of
        its full sentence.

        Public (not `_build_query`) so EvidenceRetriever can call it to
        report the exact query it is about to send via `on_phase` before
        the request goes out - see EvidenceRetriever.retrieve's
        "web_search_dispatched" event. `search()` below calls this same
        method, so the two can never drift apart.

        The sentence-as-query approach sent whatever grammatical claim
        the NLP stack extracted - stopwords, articles and all - straight
        to SearXNG as a bag of words, competing against ordinary
        few-word user queries on whatever engines SearXNG merges. The
        entities in `claim.entities` are exactly the terms that pin a
        claim to a checkable real-world fact (who, what organization,
        where); searching for those directly, quoted so a multi-word
        name isn't split across unrelated pages, is a closer match to
        how a person would actually search to verify the claim.

        Figures the entity extractor doesn't label (percentages, years -
        see FIGURE_PATTERN above) are appended for the same reason: "35%"
        or "2024" is often what separates the real event from a similar
        one.

        Falls back to the full sentence when there is nothing to anchor
        on - no entities (EntityExtractor degrades to `{}` on an
        inference outage, see entities.py) and no figures - rather than
        sending an empty query.
        """

        terms: list[str] = []
        seen: set[str] = set()

        for mentions in claim.entities.values():

            for mention in mentions:

                mention = mention.strip()
                key = mention.casefold()

                if not mention or key in seen:
                    continue

                seen.add(key)
                terms.append(f'"{mention}"' if " " in mention else mention)

        for figure in self.FIGURE_PATTERN.findall(claim.text):

            key = figure.casefold()

            if key in seen:
                continue

            seen.add(key)
            terms.append(figure)

        return " ".join(terms) if terms else claim.text.strip()

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:

        if not value:
            return None

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
