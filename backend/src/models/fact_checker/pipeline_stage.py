from enum import Enum


class PipelineStage(str, Enum):
    """
    The 7 stages of the fact-checking pipeline (see CLAUDE.md's
    fact-checking spec, §2.4). Attached to a claim (or the whole article,
    for the admission filter) to record how far it got before something
    rejected, downgraded, or otherwise stopped it.
    """

    ADMISSION_FILTER = "admission_filter"
    CLAIM_SELECTION = "claim_selection"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    EVIDENCE_RANKING = "evidence_ranking"
    LLM_VERIFICATION = "llm_verification"
    CONFIDENCE_RECALIBRATION = "confidence_recalibration"
    AGGREGATION = "aggregation"
