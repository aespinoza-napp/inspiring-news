from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, Field


class DataLayer(str, Enum):
    """
    The three storage layers every analysed article passes through.

    RAW           - exactly what was fetched, before any interpretation.
    PROCESSED     - the enriched article plus its fact-check report.
    EXPLOITATION  - the flat, denormalised, ready-to-serve document.

    Each layer is derived *only* from the one above it, and every record
    records which record it was derived from (Lineage.parent_record_id),
    so any exploitation document can be walked back to the exact bytes
    that produced it.
    """

    RAW = "raw"
    PROCESSED = "processed"
    EXPLOITATION = "exploitation"


def build_record_id(
    layer: DataLayer,
    article_id: str,
    run_id: str,
) -> str:
    """
    Deterministic record id: the same (layer, article, run) triple always
    produces the same id. Re-running a persist step therefore overwrites
    its own previous record instead of accumulating near-duplicates, which
    makes the whole persist stage idempotent and safely retryable.
    """

    return uuid5(
        NAMESPACE_URL,
        f"{layer.value}|{article_id}|{run_id}",
    ).hex


class Lineage(BaseModel):
    """
    Provenance stamped onto every record in every layer. This is what
    makes the lake traceable: given any record you can answer "which run
    produced this, from which upstream record, from which source bytes,
    with which model versions, when".
    """

    run_id: str

    article_id: str

    layer: DataLayer

    source_url: str

    # sha256 of the raw article body. Identical across all three layers
    # of one run, so it doubles as the join key between layers and as a
    # content-level dedupe key across runs.
    content_hash: str

    produced_at: datetime = Field(default_factory=datetime.now)

    parent_layer: Optional[DataLayer] = None

    parent_record_id: Optional[str] = None

    pipeline_version: str = "1"

    # Short git revision of the code that produced the record, when it
    # can be determined. None outside a git checkout (e.g. a container
    # built from a tarball) - traceability degrades, it doesn't break.
    code_revision: Optional[str] = None

    # Thresholds that differ from the environment defaults for this run.
    # Only the differences, so a record does not restate a dozen values
    # that are just "whatever .env says", and a tuned run is obvious at
    # a glance. Empty means the run used the configured defaults.
    # `int | float`, not plain `float`: a count knob such as
    # max_claims_per_article would otherwise be coerced to 2.0 in the
    # stored record, quietly changing an integer setting's type in the
    # one place whose job is to record faithfully what a run used.
    threshold_overrides: dict[str, int | float] = Field(default_factory=dict)

    # Named versions of the components that shaped this record, e.g.
    # {"embedding_model": "...", "llm_model": "...", "sentiment_model": "..."}.
    # Without this, a record's numbers are unreproducible the moment a
    # model is swapped in settings.
    components: dict[str, str] = Field(default_factory=dict)


class RunContext(BaseModel):
    """
    Identifies one execution of the pipeline. Created once per analyse
    call and threaded through all three layers, so every record written
    during that execution shares a run_id.
    """

    run_id: str

    url: str

    started_at: datetime = Field(default_factory=datetime.now)

    pipeline_version: str = "1"

    code_revision: Optional[str] = None

    threshold_overrides: dict[str, int | float] = Field(default_factory=dict)

    components: dict[str, str] = Field(default_factory=dict)
