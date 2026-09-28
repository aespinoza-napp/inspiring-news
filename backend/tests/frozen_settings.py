"""
The class attributes that read `settings` once, at import - the declared
exceptions in test_invariants.py's FROZEN_SETTINGS_EXCEPTIONS - and the
setting each one froze.

`pinned_settings` resets the live settings object, but these copies were
taken before it ran, from whatever `.env` held at import. So until this
existed every numeric assertion about ranking or confidence ran on the
local `.env`'s weights, not the declared ones - and the committed
`.env-example` shipped ranking weights summing to 1.2.

`conftest.pinned_settings` pins each of these to its declared default;
`test_invariants.py` fails when a class freezes a setting that is not
listed here.
"""

FROZEN_SETTINGS = {
    "src.services.fact_checker.ranking.ranking_retrieval.EvidenceRanker": {
        "SEMANTIC_WEIGHT": "RANKING_SEMANTIC_WEIGHT",
        "LEXICAL_WEIGHT": "RANKING_LEXICAL_WEIGHT",
        "RECENCY_WEIGHT": "RANKING_RECENCY_WEIGHT",
        "RELIABILITY_WEIGHT": "RANKING_RELIABILITY_WEIGHT",
        "DEFAULT_RELIABILITY": "RANKING_DEFAULT_RELIABILITY",
        "PERTINENCE_SEMANTIC_WEIGHT": "PERTINENCE_SEMANTIC_WEIGHT",
        "PERTINENCE_LEXICAL_WEIGHT": "PERTINENCE_LEXICAL_WEIGHT",
        "RECENCY_HALF_LIFE_DAYS": "EVIDENCE_RECENCY_HALF_LIFE_DAYS",
    },
    "src.services.fact_checker.verification.confidence_scorer.ConfidenceScorer": {
        "LLM_WEIGHT": "CONFIDENCE_LLM_WEIGHT",
        "EVIDENCE_WEIGHT": "CONFIDENCE_EVIDENCE_WEIGHT",
    },
}
