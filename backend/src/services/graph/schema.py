"""
The graph's schema, declared once.

Three things read this rather than keeping their own copy: GraphWriter
(the uniqueness constraints it creates, the entity type labels it may
set), GraphReader (the schema view merges live counts into it) and the
frontend's /graph page (which draws it). A label or relationship that is
written but not declared here is caught by tests/services/graph/.

Every relationship the pipeline or the labeller writes carries `method`
- "pipeline" or "manual" - so a hand label and the model's verdict on the
same claim sit side by side instead of one overwriting the other, and a
re-analysis replaces only what the pipeline wrote.
"""

import re

PIPELINE = "pipeline"

MANUAL = "manual"


# label -> the property MERGE keys on (and a uniqueness constraint holds).
NODE_KEYS: dict[str, str] = {
    "Article": "url",
    "Entity": "key",
    "Topic": "name",
    "Claim": "id",
    "Verdict": "name",
    "Evidence": "url",
    "Source": "domain",
}


NODES: list[dict] = [
    {
        "label": "Article",
        "key": "url",
        "description": (
            "A news item: one the pipeline analysed, or one a hand-labelled "
            "fact was taken from. Keyed by URL, so both meet on one node."
        ),
        "properties": [
            "url", "title", "language", "published_at", "analyzed_at",
            "admitted", "skipped_reason", "overall_verdict",
            "overall_confidence", "sentiment_label", "impact_score",
            "claims_total", "claims_selected", "content_hash", "run_id",
            "labelled",
        ],
    },
    {
        "label": "Entity",
        "key": "key",
        "description": (
            "Someone or something an article or claim names. Also carries "
            "its type as a second label - :Person, :Country, :Organization..."
        ),
        "properties": ["key", "name", "type"],
    },
    {
        "label": "Topic",
        "key": "name",
        "description": "One of the configured topics (src/config/topics.py).",
        "properties": ["name"],
    },
    {
        "label": "Claim",
        "key": "id",
        "description": (
            "A checkable sentence. Keyed by a hash of its normalised text, "
            "so the same sentence in two articles is one claim."
        ),
        "properties": ["id", "text", "language", "claim_type", "fact_id"],
    },
    {
        "label": "Verdict",
        "key": "name",
        "description": "TRUE, PARTIALLY_TRUE, MISLEADING, FALSE or UNVERIFIED.",
        "properties": ["name"],
    },
    {
        "label": "Evidence",
        "key": "url",
        "description": "A page a claim was checked against.",
        "properties": ["url", "title", "origin", "published_at"],
    },
    {
        "label": "Source",
        "key": "domain",
        "description": (
            "A publisher, by domain. Both articles and evidence point at it; "
            "`configured` says whether it is one of data/sources/*.yaml."
        ),
        "properties": [
            "domain", "name", "source_id", "configured", "reliability",
            "reliability_known", "language", "country", "source_type",
        ],
    },
]


RELATIONSHIPS: list[dict] = [
    {
        "type": "PUBLISHED_BY",
        "from": "Article",
        "to": "Source",
        "description": "Where the article was published.",
        "properties": [],
    },
    {
        "type": "MENTIONS",
        "from": "Article",
        "to": "Entity",
        "description": "An entity the article names (GLiNER).",
        "properties": ["method"],
    },
    {
        "type": "ABOUT",
        "from": "Article",
        "to": "Topic",
        "description": "A topic the article was classified under, or labelled with.",
        "properties": ["method", "confidence", "rank", "fact_id"],
    },
    {
        "type": "CONTAINS_CLAIM",
        "from": "Article",
        "to": "Claim",
        "description": "A claim extracted from, or labelled in, the article.",
        "properties": [
            "method", "confidence", "opinion_score", "anchor_score",
            "selected", "stage_note", "fact_id",
        ],
    },
    {
        "type": "MENTIONS",
        "from": "Claim",
        "to": "Entity",
        "description": "An entity the claim itself names.",
        "properties": ["method"],
    },
    {
        "type": "HAS_VERDICT",
        "from": "Claim",
        "to": "Verdict",
        "description": (
            "The claim's verdict - one edge per method, so the pipeline's "
            "and the annotator's can be compared directly."
        ),
        "properties": [
            "method", "confidence", "explanation", "raw_verdict",
            "checked_at", "reached_stage", "independent_domains",
            "llm_unreachable", "search_unavailable", "fact_id", "label_raw", "annotator_note",
            "reviewed", "source_tier", "evidence_date",
        ],
    },
    {
        "type": "CHECKED_AGAINST",
        "from": "Claim",
        "to": "Evidence",
        "description": (
            "A source the claim was verified against: ranked evidence for "
            "the pipeline, reference links for a hand label."
        ),
        "properties": [
            "method", "cited", "stance", "quote", "relevance",
            "pertinence", "reliability", "fact_id",
        ],
    },
    {
        "type": "PUBLISHED_BY",
        "from": "Evidence",
        "to": "Source",
        "description": "Where the evidence page was published.",
        "properties": [],
    },
]


# GLiNER's labels (src/processors/nlp/entities.py DEFAULT_LABELS) to the
# second label an Entity node carries. Cypher cannot take a label as a
# parameter, so a label is spliced into the query text - which is why it
# only ever comes from this table or passes SAFE_LABEL, never straight
# from model output.
ENTITY_TYPE_LABELS: dict[str, str] = {
    "person": "Person",
    "organization": "Organization",
    "location": "Location",
    "country": "Country",
    "city": "City",
    "company": "Company",
    "product": "Product",
    "event": "Event",
}

SAFE_LABEL = re.compile(r"^[A-Z][A-Za-z0-9]{0,40}$")


def entity_label(entity_type: str) -> str | None:
    """
    The type label for an entity, or None when the type cannot be made
    into a safe one - the node is still written, as a plain :Entity.
    """

    label = ENTITY_TYPE_LABELS.get(entity_type)

    if label is None:
        label = "".join(part.capitalize() for part in re.split(r"[\s_-]+", entity_type))

    if not SAFE_LABEL.match(label) or label in NODE_KEYS:
        return None

    return label


def constraint_statements() -> list[str]:
    return [
        f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
        f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
        for label, key in NODE_KEYS.items()
    ]


def declared_schema() -> dict:
    return {
        "nodes": NODES,
        "relationships": RELATIONSHIPS,
        "entityTypes": ENTITY_TYPE_LABELS,
        "methods": [PIPELINE, MANUAL],
    }
