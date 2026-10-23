"""The questions the pipeline's decisions are asked as, for Laya.

Laya (`inference/`, `docs/decisions/laya.md`) answers typed questions
about a text - `choice`, `score`, `noul` - in one forward pass. A
fine-tuned checkpoint has learnt *these* questions: the option names and
their descriptions are what each option's marker is matched against, so
changing a word here changes what a trained checkpoint is being asked.
Training (`src/evaluation/decisions.py`) and the pipeline read them from
here, never from a copy.

Written 2026-10-23, before any run on this project's data
(`data/evaluation/experiments/laya/rule.md`).
"""

from src.config.topics import TOPIC_GROUPS, TOPICS

# D1. The labels' own scale (experiments/alignment, ranking, emphasis):
# 0 not worth offering, 1 worth offering, 2 clearly positive. A score
# question's criteria run lowest first; the answer is the expected level.
WORTH_OFFERING = {
    "type": "score",
    "instructions": (
        "How worth offering is this news story to a publication of "
        "constructive, positive-impact news?"
    ),
    "criteria": [
        "not worth offering: politics, strikes, crime, war, disasters, markets, "
        "celebrity, sport, service pages, opinion, product news, index pages",
        "worth offering: plain science, history or culture",
        "clearly positive: a real improvement, a solution, progress, a discovery "
        "with a use, people helping",
    ],
}


def candidate_state(title: str, summary: str | None) -> str:
    """What D1 reads: a candidate's feed title and summary, as trained."""
    title = (title or "").strip()
    summary = (summary or "").strip()
    return f"{title}\n{summary}" if summary else title


def _group_description(group: str) -> str:
    return ", ".join(TOPICS[topic].name for topic in TOPIC_GROUPS[group])


# D2. The five groups, each described by its topics' names.
TOPIC_GROUP_QUESTION = {
    "type": "choice",
    "instructions": "Which group of topics is this news story about?",
    "criteria": {group: _group_description(group) for group in TOPIC_GROUPS},
}

# D3. The labelling batch's keep-or-skip: kept sentences became facts,
# skipped ones were opinion, fragment, trivial, prediction or duplicate.
CHECKABLE_CLAIM = {
    "type": "noul",
    "instructions": (
        "Does the sentence state a fact about the past or present that "
        "could be checked against other sources?"
    ),
}

# D4. The per-source verifier's own stances and definitions
# (verification/per_source.py, PER_SOURCE_SYSTEM_PROMPT), so a Laya
# stance and an LLM stance mean the same thing.
SOURCE_STANCE = {
    "type": "choice",
    "instructions": "What does the source say about the claim?",
    "criteria": {
        "supports": "the source states what the claim says: its point, and its figures, dates and names",
        "contradicts": "the source states something that cannot be true at the same time as the claim: "
                       "another figure, date, person or outcome for the same thing",
        "silent": "the source is about the claim's subject but does not say whether the claim is true",
        "unrelated": "the source is about a different event or subject",
    },
}

DECISIONS = {
    "worth_offering": WORTH_OFFERING,
    "topic_group": TOPIC_GROUP_QUESTION,
    "checkable_claim": CHECKABLE_CLAIM,
    "source_stance": SOURCE_STANCE,
}
