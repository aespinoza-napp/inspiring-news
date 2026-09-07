# NLP processors

Deterministic, model-backed text transformations run by `src/workflows/enrichment.py`
(`NewsEnrichmentPipeline`) to turn a raw `News` into an `EnrichedArticle`. Each processor implements
`base.py`'s `BaseProcessor.process(text) -> Any` and owns exactly one concern:

| File | Produces | Notes |
|---|---|---|
| `keywords.py` | `list[str]` | |
| `entities.py` | named entities | Uses GLiNER |
| `claims.py` | `list[Claim]` | Scores sentences for verifiability signals (named entities, numbers, dates, reporting verbs, quotes) and discards ones below threshold — see `ClaimSelector` in `services/fact_checker/` for what happens to these downstream |
| `classifier.py` | `list[TopicPrediction]` | Topic classification against a fixed topic set |
| `sentiment.py` | `SentimentResult` | HuggingFace sequence-classification model (multilingual) — positive/neutral/negative + polarity/subjectivity/confidence |
| `quality.py` | `Quality` | Lexicon-based heuristics: constructiveness, inspirational value, hope, objectivity, societal impact, readability, novelty — feeds `PositiveImpactValidator`'s admission-gate score |
| `embeddings.py` | vector | Thin wrapper; the actual model singleton lives in `src/services/embeddings/service.py` (`EmbeddingService`) — that's what everything else in the codebase should import, not this file directly |

These are all real, local models (no LLM calls) — cheap enough to run on every article. The one LLM
call in the whole pipeline happens later, per-claim, in `services/fact_checker/verification/`.

`GLiNER`, `sentence-transformers`, and the sentiment classifier are loaded eagerly the first time
`NewsEnrichmentPipeline` is constructed — real seconds of work, which is why `src/container.py`
constructs it lazily (see `CLAUDE.md`'s "Lazy construction, on purpose" section).
