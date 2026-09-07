# Models

Pydantic (and one plain-dataclass) models, organized by **domain** rather than dumped in one flat
directory — each subpackage roughly mirrors a subsystem under `src/services/` or `src/processors/`.
No `__init__.py` anywhere here or elsewhere in `src/` — everything is a namespace package.

| Subpackage | Contents | Used by |
|---|---|---|
| `core/` | `news.py`, `source.py`, `claim.py` (+ `RejectedClaim`), `enriched_article.py`, `similarity.py`, `job.py` | Types shared across multiple subsystems — the "nouns" of the pipeline |
| `nlp/` | `sentiment_result.py`, `quality.py`, `topic_prediction.py`, `topics.py` | Output shapes for `src/processors/nlp/` |
| `scraper/` | `extraction.py` | `src/services/scraper/` |
| `fact_checker/` | `evidence.py` (+ `RejectedEvidence`), `fact_check.py`, `fact_check_report.py`, `validation_result.py`, `duplicate_result.py`, `pipeline_stage.py` | `src/services/fact_checker/` — mirrors that directory's own layout |
| `corrector/` | `correction_metric.py` | `src/services/corrector/` |

A few worth knowing about specifically:

- **`core/enriched_article.py`** (`EnrichedArticle`) is the central object the whole pipeline builds
  and passes around: a `News` plus keywords, entities, topics, claims, sentiment, quality, and an
  embedding, all attached.
- **`fact_checker/pipeline_stage.py`** (`PipelineStage`) is a `str, Enum` of the 7 fact-checking stages
  (see the `fact_checker/` service README) — used to tag exactly where a claim stopped, not just
  whether it passed.
- **`fact_checker/evidence.py`** has both `Evidence` (a source actually used) and `RejectedEvidence`
  (a source that was found but discarded, tagged with the `PipelineStage` it was cut at and why).

If you add a new model, put it in the subpackage matching the subsystem that owns it — don't start a
new top-level file in `models/` directly.
