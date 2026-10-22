import math
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Each group is one scoring function's weights, and each must sum to 1.0.
# That used to be a comment only: setting CONFIDENCE_LLM_WEIGHT=0.8 in
# .env alone produced a confidence of up to 1.1 before the clamp, and
# nothing said so. Now it refuses to start.
WEIGHT_GROUPS = {
    "ranking": (
        "RANKING_SEMANTIC_WEIGHT", "RANKING_LEXICAL_WEIGHT",
        "RANKING_RECENCY_WEIGHT", "RANKING_RELIABILITY_WEIGHT",
    ),
    "pertinence": ("PERTINENCE_SEMANTIC_WEIGHT", "PERTINENCE_LEXICAL_WEIGHT"),
    "confidence": ("CONFIDENCE_LLM_WEIGHT", "CONFIDENCE_EVIDENCE_WEIGHT"),
}


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    STORAGE_PATH: Path = Path("data")

    RAW_PATH: Path = STORAGE_PATH / "raw"

    PROCESSED_PATH: Path = STORAGE_PATH / "processed"

    EMBEDDINGS_PATH: Path = STORAGE_PATH / "embeddings"

    FACT_CHECK_PATH: Path = STORAGE_PATH / "fact_checks"

    GRAPH_PATH: Path = STORAGE_PATH / "graph"

    CACHE_PATH: Path = STORAGE_PATH / "cache"

    # Three-layer storage lake (raw -> processed -> exploitation).
    # Deliberately *not* the legacy RAW_PATH/PROCESSED_PATH scratch
    # directories above: those hold bare News/EnrichedArticle JSON
    # written ad hoc by scripts and tests, while the lake holds
    # lineage-stamped records and must not be mixed with them.
    LAKE_PATH: Path = STORAGE_PATH / "lake"

    # Whether the pipeline writes to the lake at all. Off makes
    # AnalysisService pure (no side effects) for tests/dry runs.
    LAKE_ENABLED: bool = True

    # The newsroom's articles in progress, one JSON file each
    # (src/services/writer/draft_store.py). Beside the lake, not in it:
    # the lake records what was found and checked; a draft is edited in
    # place. Created on the first save, not here.
    DRAFTS_PATH: Path = STORAGE_PATH / "drafts"

    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr

    # Whether a finished analysis is also written into the Neo4j graph
    # (src/services/graph/). A side effect like the lake, and fail-soft
    # like it: Neo4j being down costs one short connection timeout per
    # run and a `graph_failed` event, never the analysis. Off skips the
    # write entirely; the /graph read endpoints still answer.
    GRAPH_ENABLED: bool = True

    # Documentary, not load-bearing: the model itself now loads inside
    # inference/ (inference/src/config.py's own SENTIMENT_MODEL), not
    # here. Kept so a human reading .env still sees what's running.
    # Changing this value does NOT change behavior - change
    # inference/src/config.py's default (or that service's own env) and
    # rebuild/restart it instead.
    SENTIMENT_MODEL: str = (
        "cardiffnlp/twitter-xlm-roberta-base-sentiment"
    )

    # Qdrant settings
    QDRANT_PATH: Path = Path("data/vector_db")

    # Still load-bearing: VectorRepository sizes the Qdrant collection
    # from this, independent of which embedding model actually produces
    # the vectors (see backend/tests/services/test_embeddings.py's
    # config-drift test for why the two must actually agree).
    EMBEDDING_DIMENSION: int = 1024

    # Documentary only, same caveat as SENTIMENT_MODEL above - the model
    # loads in inference/src/config.py now.
    EMBEDDING_MODEL: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    # The model server for GLiNER/sentiment/embeddings (inference/) -
    # see backend/src/services/inference_client.py. Defaults to
    # localhost for running both services on the host during local dev,
    # same pattern as LLM_BASE_URL below; docker-compose.yml overrides
    # this to the container DNS name.
    INFERENCE_URL: str = "http://localhost:8001"
    INFERENCE_TIMEOUT: float = 30.0

    # How many /analyze/jobs runs (single or batch) may execute at once.
    # A process resource limit, not a per-run pipeline threshold - each
    # run still does real scraping, inference/ HTTP calls, a SearXNG
    # search and an LLM call, so unbounded concurrency here is what
    # overloads those, not the pipeline logic itself. See
    # src/services/job_queue.py.
    ANALYSIS_MAX_CONCURRENCY: int = 3

    # -----------------------------------------------------------------
    # Fan-out and resource ceilings (see src/services/concurrency.py)
    #
    # Fact-checking runs claims concurrently, and each claim runs its two
    # searches and its page fetches concurrently too. Those multiply -
    # ANALYSIS_MAX_CONCURRENCY x CLAIM_MAX_CONCURRENCY x
    # SCRAPE_MAX_CONCURRENCY is the worst case - so the fan-out numbers
    # are chosen for what is sensible to watch at once and the real
    # ceiling is the per-resource limit below, applied once per process.
    #
    # Infrastructure, not per-run tunables: a request must not be able to
    # raise how hard this process hits a service every other request
    # shares. Same reasoning as ANALYSIS_MAX_CONCURRENCY above.
    # -----------------------------------------------------------------

    # How many of an article's claims are verified at the same time.
    CLAIM_MAX_CONCURRENCY: int = 4

    # Finished jobs kept in memory once the journal holds them (JobStore):
    # the rest are served from the journal by id. Memory, not a run's
    # judgement - infrastructure, listed in NON_THRESHOLD_SETTINGS.
    JOB_STORE_KEEP_FINISHED: int = 200

    # How long an analysis stays cached (AnalysisCache), in hours; 0 or
    # less never expires. A verdict rests on that day's web search, and a
    # duplicate rejection on what the corpus held: a week, not forever.
    # Infrastructure, in NON_THRESHOLD_SETTINGS: it says when to recompute,
    # not how a run judges.
    ANALYSIS_CACHE_TTL_HOURS: float = 168

    # How many of one claim's queries are sent at the same time. Two is
    # the whole set today (affirmative + refutation).
    QUERY_MAX_CONCURRENCY: int = 2

    # Zero or below means unbounded, for tests and single-user local runs.
    #
    # SearXNG was 4. It fans every request out to each upstream engine,
    # and those rate-limit by IP: a single analysis (3 queries x 2-4
    # claims) arriving four at a time got Brave suspended for "too many
    # requests", and on 2026-09-28 Brave, Yep and Semantic Scholar were
    # suspended within four back-to-back queries. Fewer at once, plus
    # SearxngClient answering repeated queries once, is fewer suspensions.
    SEARXNG_MAX_CONCURRENCY: int = 2
    SCRAPE_MAX_CONCURRENCY: int = 8

    # Inference was 4. On a CPU the embedding model gains almost nothing
    # from running batches side by side, and each one waits for the
    # others: measured 2026-10-13 from the backend container, one batch
    # of 16 evidence pages took 11.9 s alone and 43 s with four at once
    # (43 s wall, against 48 s one after another), past INFERENCE_TIMEOUT's
    # 30 s. An analysis failed on exactly that. The wait for a permit
    # happens here, before the request is sent, so it is not timed.
    INFERENCE_MAX_CONCURRENCY: int = 1
    LLM_MAX_CONCURRENCY: int = 2

    # Headless browsers rendering at once - the last step of the
    # extraction cascade, and by far its most expensive: each is a
    # Chromium process with its own memory, CPU and page load. Kept
    # small; a page only gets here when both HTML parsers failed.
    BROWSER_MAX_CONCURRENCY: int = 2

    # -----------------------------------------------------------------
    # Pipeline thresholds
    #
    # These are the *defaults*. A single run can override any of them
    # per request (see src/config/thresholds.py and the `thresholds`
    # field on POST /analyze and POST /analyze/jobs); anything the
    # caller leaves out falls back to the value below.
    #
    # Read them through a PipelineThresholds instance, never as a class
    # attribute evaluated at import time - `MIN_X = settings.MIN_X` in a
    # class body freezes the value when the module is first imported,
    # which is why per-run overrides (and even plain env changes under
    # some import orders) had no effect before.
    # -----------------------------------------------------------------

    # -----------------------------------------------------------------
    # Fetch guard (SSRF)
    #
    # Every fetch is server-side with a URL from outside the process, so
    # without this the service proxies into whatever network it runs on -
    # including the compose network that holds Neo4j and SearXNG, and any
    # cloud metadata endpoint. Off is for offline tests only.
    # -----------------------------------------------------------------
    URL_GUARD_ENABLED: bool = True

    # Hostnames exempt from the private-address check. Empty by default;
    # an escape hatch for a staging host on a private network, so nobody
    # reaches for URL_GUARD_ENABLED=false to solve that.
    URL_GUARD_ALLOWED_HOSTS: list[str] = []

    # When set, /storage/* requires this value in an X-API-Key header.
    # Unset leaves those endpoints open, which is fine on localhost and
    # not fine anywhere else - src/main.py logs a warning at startup so
    # that choice is never silent.
    STORAGE_API_KEY: SecretStr | None = None

    # "text" for a terminal, "json" for a log shipper: one object per
    # line, the job runner's phase timings as fields
    # (src/services/log_format.py). docker-compose.prod.yml sets json.
    LOG_FORMAT: Literal["text", "json"] = "text"

    # Enrichment
    TOPIC_CLASSIFIER_THRESHOLD: float = 0.35
    ENTITY_THRESHOLD: float = 0.50
    CLAIM_MIN_CONFIDENCE: float = 0.50

    # Above this, a sentence reads as opinion/interpretation and is not
    # extracted as a claim at all. Deliberately permissive: news prose is
    # full of mild evaluative language, and a low ceiling here throws away
    # checkable sentences that merely sound enthusiastic.
    OPINION_MAX_SCORE: float = 0.50

    # Extraction: shortest body accepted as a real article, in characters
    MIN_BODY_LENGTH: int = 500

    # Admission filter
    TOPIC_MIN_CONFIDENCE: float = 0.35
    POSITIVE_IMPACT_MIN_SCORE: float = 0.1

    # Whether low objectivity / strong negative sentiment reject an
    # article outright, on top of costing it score. See
    # PositiveImpactScorer.score.
    POSITIVE_IMPACT_HARD_FAIL_ENABLED: bool = False

    # Similarity threshold for duplicate detection
    DUPLICATE_THRESHOLD: float = 0.90
    RELATEDNESS_THRESHOLD: float = 0.80

    # SearXNG (self-hosted meta-search, used for fact-check evidence retrieval)
    SEARXNG_URL: str = "http://localhost:8080"
    SEARXNG_TIMEOUT: float = 10.0
    SEARXNG_MAX_RESULTS: int = 8

    # DuckDuckGo's keyless HTML results page, asked only when SearXNG
    # cannot answer a query (src/services/duckduckgo.py). A second route
    # that needs no API key. One request at a time: it refuses by IP, and
    # it is only ever asked when something is already failing.
    DUCKDUCKGO_FALLBACK_ENABLED: bool = True
    DUCKDUCKGO_URL: str = "https://html.duckduckgo.com/html/"
    DUCKDUCKGO_TIMEOUT: float = 10.0
    DUCKDUCKGO_MAX_CONCURRENCY: int = 1

    # LLM (OpenAI-compatible chat completions; defaults to a local Ollama
    # instance so verification is free/open-source by default. Swapping to
    # Groq/OpenRouter/Together/real OpenAI is a settings-only change.
    # llama3.2:3b replaced llama3.1 (8B) as the default: same Ollama/OpenAI
    # wire format, a third of the weights to load alongside inference/'s
    # GLiNER + sentiment + bge-m3, and noticeably faster per-claim
    # verification on a laptop with no GPU. Phase 5 still owns measuring
    # whether it verifies as well - this is a resource swap, not a
    # benchmarked upgrade.
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_API_KEY: SecretStr = SecretStr("ollama")
    LLM_MODEL: str = "llama3.2:3b"
    # Halved from 60s now that the default model is 3B, not 8B - a stuck
    # request still costs at most 2 x this (complete_json's own retry;
    # the SDK's own retries are off, see LLMClient).
    LLM_TIMEOUT: float = 30.0
    # One AI selection call scores a batch of candidates and writes a
    # reason for each - several times a verdict's output. Measured
    # 2026-10-05 on llama3.1 (8B, local GPU): 13 candidates took 72s, so
    # LLM_TIMEOUT's 30s failed every selection. Its own limit, for the
    # same reason LLM_TIMEOUT has one: a request the model cannot finish
    # in time is retried once and then the whole selection fails, loudly.
    AI_SELECTION_TIMEOUT: float = 240.0
    # The writer (docs/decisions/writing.md): its own model, because the
    # one that verifies claims was chosen for speed per claim, and writing
    # in Catalan, Spanish and English from long source prompts asks for
    # something else. None means LLM_MODEL. Same base URL and key: one
    # self-hosted Ollama serves both.
    WRITER_LLM_MODEL: str | None = None
    # A whole article is many times a verdict's output; LLM_TIMEOUT's 30s
    # would fail every one. Its own limit, as AI_SELECTION_TIMEOUT is.
    WRITER_LLM_TIMEOUT: float = 300.0
    # The model that reviews a draft. None means LLM_MODEL. Kept apart
    # from the writer's so a draft need not be judged by the model that
    # wrote it.
    CORRECTOR_LLM_MODEL: str | None = None
    # How the review's proposed correction is asked for: `rewrite`, the
    # whole article written out again, or `edits`, only the changes to it,
    # applied where each passage occurs exactly once and then checked like
    # any proposal (services/corrector/draft_reviewer.py). Measured
    # 2026-10-21: edits halved the correction of a draft with a few planted
    # defects and took 65% more tokens on a draft the writer wrote, where
    # nearly every sentence changes and each edit copies its sentence
    # twice. Hence `rewrite`. docs/decisions/performance.md.
    REVIEW_CORRECTION: Literal["rewrite", "edits"] = "rewrite"
    # Per model, the `reasoning_effort` sent with every call to it, as
    # JSON: {"qwen3.5:4b": "none"}. For hybrid reasoning models, which
    # think before every answer unless told not to - minutes more per
    # draft on a CPU. Ollama's OpenAI endpoint takes "none" as "do not
    # think" (docs.ollama.com/api/openai-compatibility); Qwen3.5 dropped
    # Qwen3's /no_think soft switch, so the request is the only way.
    # A model not named here gets nothing, as before.
    LLM_REASONING_EFFORT: dict[str, str] = {}
    # Base delay before complete_json's retry after a connection/timeout
    # failure, doubled each attempt and capped at 5s.
    LLM_RETRY_BACKOFF_SECONDS: float = 0.5

    # The writer's per-draft defaults. Read only through WriterThresholds
    # (src/config/thresholds.py), so one draft can be asked for with other
    # values; docs/decisions/writing.md, "Writing".
    #
    # How many articles from other outlets on the same story the writer is
    # given, at most, and how far before the analysed article one may be
    # dated and still count as the same story.
    WRITER_RELATED_MAX_SOURCES: int = 5
    WRITER_RELATED_MAX_AGE_DAYS: int = 30
    # How much of each source the writer sees, in characters. The writer
    # sees excerpts, never whole pages: the excerpt is also what a review
    # can hold the draft to. The analysed article gets more - it is the
    # story the draft is about.
    WRITER_RELATED_EXCERPT_CHARS: int = 1500
    WRITER_ANALYSED_EXCERPT_CHARS: int = 6000
    # The evidence behind the analysed article's verdicts: cited sources
    # only, a few lines each around the passage the verdict was judged on.
    WRITER_EVIDENCE_MAX_SOURCES: int = 6
    WRITER_EVIDENCE_EXCERPT_CHARS: int = 600
    # The writer's answer, in tokens: an article of 600-900 words plus its
    # metadata is ~1,500-2,500 in Catalan or Spanish. A ceiling, so a small
    # model stuck repeating itself stops instead of running to the timeout.
    WRITER_MAX_OUTPUT_TOKENS: int = 4096
    # The whole prompt, in characters (~3.5-5 per token in Catalan,
    # Spanish and English). Excerpts are shortened to fit. Sized for a
    # model served with a 16k-token context, which must be configured:
    # Ollama with none set evaluated 30,000 characters as 2,050 tokens and
    # said nothing (measured 2026-10-15; docs/decisions/writing.md).
    WRITER_PROMPT_MAX_CHARS: int = 30000

    # Claim selection
    CLAIM_DEDUP_THRESHOLD: float = 0.92

    # The anchor band - how many load-bearing claims actually get verified.
    ANCHOR_CLAIMS_MIN: int = 2
    ANCHOR_CLAIMS_MAX: int = 4

    # Distinct domains needed before a claim counts as corroborated.
    MIN_INDEPENDENT_DOMAINS: int = 2

    # Evidence retrieval / ranking
    EVIDENCE_FETCH_CANDIDATES: int = 8
    MAX_EVIDENCE_PER_CLAIM: int = 5
    EVIDENCE_RECENCY_HALF_LIFE_DAYS: float = 365.0
    MIN_EVIDENCE_FOR_VERDICT: int = 1

    # The pertinence floor: below this, a source is topically related but
    # does not address the assertion, and is cut before the LLM ever sees
    # it. Deliberately low - this is a floor against off-target retrieval,
    # not a relevance ranking, and cutting real evidence here turns a
    # checkable claim into UNVERIFIED.
    EVIDENCE_MIN_PERTINENCE: float = 0.25

    # The second look (services/fact_checker/second_look.py): a second,
    # wider search for a claim whose first verdict is in doubt - UNVERIFIED,
    # or below this confidence. Off until the tuning half of the custom set
    # says it helps (docs/decisions/evaluation.md, "The second look").
    SECOND_LOOK_ENABLED: bool = False
    SECOND_LOOK_BELOW_CONFIDENCE: float = 0.5

    # What the verifier reads of each source (verification/excerpts.py):
    # `head` (the page's first VERIFIER_EXCERPT_CHARS characters) or
    # `passages` (the sentences carrying the claim's terms, within the same
    # budget). Every run until 2026-10-21 read the head at 1500. Passages at
    # 700 on the train half, same pages, same day: accuracy +4.4 points
    # [-4.4, +13.2], 29.5% fewer prompt tokens a call, the call 24% faster.
    # docs/decisions/performance.md.
    VERIFIER_EXCERPT: Literal["head", "passages"] = "passages"
    VERIFIER_EXCERPT_CHARS: int = 700

    # The speed switches (2026-10-22, docs/decisions/performance.md, "The
    # 20-second fact-check"). Each default is what every run did before
    # it existed, but VERIFIER_ANSWER's, changed by the verifier experiment
    # (below); `data/evaluation/thresholds/fast.json` turns them on.
    #
    # VERIFIER_ANSWER: `full` asks for a stance and a verbatim quote per
    # source and one or two sentences (~145 answer tokens, the median);
    # `compact` for a stance per source and a short reason, no quotes
    # (~50). On a CPU the model writes 6-14 tokens a second, so the answer
    # is most of a call. `per_source` asks about one source at a time
    # (does it state the claim, state otherwise, or say nothing on it?)
    # with a stance and a quote, and the verdict is the side more outlets
    # take (verification/per_source.py). The default since the verifier
    # experiment of 2026-10-22 (data/evaluation/experiments/verifier/),
    # on the same evidence as the list verifier: natural claims 49.1 ->
    # 67.3% on the test half, confidently wrong verdicts 47 -> 29%, the
    # model's time a claim 27 -> 21 s - and claims with one altered detail
    # 60 -> 13%: it rarely catches a changed figure. `full` was the
    # default before; `thorough.json` keeps it for the harness.
    VERIFIER_ANSWER: Literal["full", "compact", "per_source"] = "per_source"
    # VERIFIER_RULES: `original` is the prompt every run had until
    # 2026-10-22, which defines neither TRUE nor FALSE and has no stance
    # for a source that is on the subject but silent on the claim's point;
    # the 3B then answered FALSE to 21 of 45 true train claims, most of them
    # explained as "the evidence does not mention ...". `stated` defines
    # each verdict by what a source states, adds the "silent" stance, and
    # the scorer holds the model to it: no FALSE without a cited source
    # that contradicts, no TRUE without one that supports.
    VERIFIER_RULES: Literal["original", "stated"] = "original"
    # EVIDENCE_PRERANK: what picks the pages worth fetching from ~20 search
    # hits. `embedding` embeds every title and snippet with bge-m3 (6.5 s a
    # claim on the CPU); `lexical` uses the claim's terms alone (no call).
    EVIDENCE_PRERANK: Literal["embedding", "lexical"] = "embedding"
    # RANKING_TEXT: what the ranker and the pertinence gate judge of each
    # source. `head` is its first 2,000 characters; `passages` exactly what
    # the verifier will read of it (VERIFIER_EXCERPT at VERIFIER_EXCERPT_CHARS):
    # shorter to embed, and the gate then judges what the model reads.
    RANKING_TEXT: Literal["head", "passages"] = "head"
    # FETCH_EVIDENCE_PAGES: false judges search snippets alone, no page
    # fetched or parsed.
    FETCH_EVIDENCE_PAGES: bool = True
    # FACT_CHECK_PROFILE: which named set of the switches below (and of the
    # query plan, the sources and their excerpt) this environment's runs
    # take as their defaults (config/thresholds.py, FACT_CHECK_PROFILES).
    # `thorough` is every default as it was; `fast` and `fast_snippets` are
    # the 2026-10-22 contest's entries C and D. One line in backend/.env
    # makes the app fast; a request's own overrides still win, and the
    # harness reads it too (it logs the profile, and the run key records
    # the thresholds it produced).
    FACT_CHECK_PROFILE: Literal["thorough", "fast", "fast_snippets"] = "thorough"
    # CLAIM_DEADLINE_SECONDS: a claim's whole check, search to verdict,
    # within this many seconds; 0 is no deadline. Pages not fetched by
    # half of it keep their snippet, and a model that has not answered by
    # the end leaves the claim "not checked" (llm_unreachable), never a
    # verdict.
    CLAIM_DEADLINE_SECONDS: int = 0

    # EvidenceRanker scoring weights (must sum to 1.0)
    #
    # RANKING_LEXICAL_WEIGHT is the newest of the four and the reason the
    # other three moved. Embedding similarity alone ranks a page *about
    # the same subject* as highly as one that addresses the assertion: a
    # claim mentioning ACME retrieved three pages explaining what the word
    # "acme" means in Greek, all at high cosine, and the model cited them
    # as confirmation. Lexical coverage of the claim's own discriminative
    # terms is what those pages have none of.
    RANKING_SEMANTIC_WEIGHT: float = 0.45
    RANKING_LEXICAL_WEIGHT: float = 0.20
    RANKING_RECENCY_WEIGHT: float = 0.20
    RANKING_RELIABILITY_WEIGHT: float = 0.15
    RANKING_DEFAULT_RELIABILITY: float = 0.5

    # How semantic and lexical agreement combine into the single
    # "does this source actually address the claim" figure that the
    # pertinence gate thresholds. Its own normalised pair, kept apart
    # from the ranking weights because it answers a different question:
    # ranking orders sources, pertinence decides whether a source is
    # allowed to support a verdict at all.
    PERTINENCE_SEMANTIC_WEIGHT: float = 0.5
    PERTINENCE_LEXICAL_WEIGHT: float = 0.5

    # ConfidenceScorer weights (must sum to 1.0)
    CONFIDENCE_LLM_WEIGHT: float = 0.7
    CONFIDENCE_EVIDENCE_WEIGHT: float = 0.3

    @model_validator(mode="after")
    def _weight_groups_sum_to_one(self) -> "Settings":

        for group, names in WEIGHT_GROUPS.items():

            weights = {name: getattr(self, name) for name in names}

            if any(weight < 0 for weight in weights.values()) or not math.isclose(
                sum(weights.values()), 1.0, abs_tol=1e-6
            ):
                raise ValueError(
                    f"The {group} weights must be non-negative and sum to 1.0, "
                    f"got {weights} (sum {sum(weights.values()):.4f}). "
                    "Change them together, in backend/.env or the environment."
                )

        return self


settings = Settings()

for folder in (
    settings.STORAGE_PATH,
    settings.RAW_PATH,
    settings.PROCESSED_PATH,
    settings.EMBEDDINGS_PATH,
    settings.FACT_CHECK_PATH,
    settings.GRAPH_PATH,
    settings.CACHE_PATH,
    settings.LAKE_PATH,
):
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )