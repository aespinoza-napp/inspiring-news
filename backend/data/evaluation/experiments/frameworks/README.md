# Frameworks compared, phase by phase

The plan of 2026-11-10 (session `d6b45b1c`): each phase of the pipeline
against the other ways of doing it - the local pipeline, local LLMs, Claude
and a person - in quality, time and cost, each on a fixed input set. Started
2026-11-11. `report.md` holds the figures (`uv run python -m
src.evaluation.frameworks report ...`, below); this file says how they were
made and what they cannot say.

## Claude is headless, never the API

Every Claude figure here is `claude -p` on the claude.ai subscription
(`src/evaluation/headless_claude.py`, `--model claude-headless:<alias>`), with
no tools, no web search, no CLAUDE.md, an empty working directory and every
API credential stripped from its environment. The harness's own prompts, JSON
parsing, retries and scoring are the ones every local model went through:
only the transport differs.

**The guard.** Every call's stream carries the plan's five-hour and seven-day
`utilization`. The run stops (a `BaseException`, so no per-claim `except`
swallows it) at **90%** of either window (`HEADLESS_CLAUDE_CEILING`), when
the account has extra credits on or is using them, when the plan refuses a
call, or when a call ran on a key. Once tripped, no later call starts.
The interactive session driving the runs uses the same windows and is not
covered by it.

**Cost.** Each call's `total_cost_usd` is logged as `apiEquivalentUsd` in
`claude-calls.jsonl`: what the same tokens would cost at API list price,
never charged. The real cost is a share of the plan, logged beside it.

## How each phase was run (2026-11-11)

| Phase | Input | Contenders | Command |
|---|---|---|---|
| Topics | the 58 articles of the 20 Oct topics experiment, text frozen once in `topics/articles.jsonl` (56 extracted; two ESA pages give nothing) | embedding classifier (the pipeline's), `llama3.2:3b-bench`, `qwen3.5:4b-bench`, Claude Haiku, Claude Sonnet | `frameworks topics-fetch`, then `frameworks topics --model <m>` |
| Fact-checking | AVeriTeC dev, the first 10 claims, the evidence kept by the knowledge-store run `49e4c76106c6` | `llama3.2:3b-bench` replayed, Claude Sonnet replayed, Claude Sonnet closed-book | `cli run --dataset data/evaluation/averitec/averitec_dev.jsonl --replay data/evaluation/runs/averitec_dev/llama3.2-3b-bench/49e4c76106c6 --thresholds data/evaluation/thresholds/averitec_store.json --model <m> --limit 10 --label replay-store` (and `--closed-book` instead of `--replay`) |
| Review | the 36 planted-defect texts (`writing/texts_en_es.jsonl`), the corrector's own prompt | the five local runs already made, Claude Sonnet | `cli writing run --model claude-headless:sonnet`, then `cli writing report --run ...` (copied to `review/`: the committed `writing/reports/` was left as it was) |
| Scraping | - | not run | needs a hand-copied body per page as the reference |
| Writing | - | not run | needs human readers judging blind; `check_article.py` checks the contract, not quality |
| Publishing | - | future work | |

Local runs need `LLM_BASE_URL=http://localhost:11434/v1` in the command's
environment while `backend/.env` points at a hosted provider (on 11 Nov it
named Groq): the harness reads `.env`, and a local model name sent there is
refused as unreachable.

## What these figures cannot say

- **Ten claims.** Every fact-checking interval spans 60 points. It is a
  check that the path works and a first reading, not a result. 7 of the 10
  gold labels are Refuted, so always answering FALSE gets 7.
- **Claude knows AVeriTeC's claims.** Closed-book, with no evidence at all,
  Claude Sonnet got 7 of 10 - more than with the evidence (5). Its training
  covers 2020-22 fact-checks. No tool reached the web, so the temporal gate
  holds for what it *read*; it cannot hold for what it *remembers*. A Claude
  verdict on AVeriTeC is therefore an upper bound, and the replay-vs-closed-book
  gap, not the replay score alone, is what speaks to its reading.
- **No temperature.** `claude -p` takes none; the local models are asked at
  0, and the 3B replayed its 5 Nov verdicts exactly (10 of 10). A Claude run
  repeated need not agree with itself.
- **Topic gold is the annotator's, partly an AI pass, unreviewed.** A Claude
  contender agreeing with labels an AI wrote measures agreement first.
- **Time is not like for like.** Local seconds are this machine's CPU (Intel Core Ultra 7 165U, 14 threads,
  no GPU, one model call at a time); Claude's are a network round trip plus
  ~1-2 s of CLI start-up per call, on Anthropic's hardware.
- **The person is missing.** No phase has a timed human run yet. The
  labeller records `activeSeconds` per fact; labelling the topic set and ten
  claims with it would give the manual column.

## Standard sets (2026-11-11, second round)

Asked for before any 100-claim run: deterministic contenders, a trained
embedding classifier, GLiNER against other entity models, English and
Spanish, on sets the community knows. Figures in `report.md`.

| Task | Set | Contenders | Command |
|---|---|---|---|
| Topics | SIB-200 test, 204 sentences, the same in `en` and `es`, 7 topics; trained ones learn from its 701 training sentences per language | bge-m3 untrained (the pipeline's method), bge-m3 + logistic regression, TF-IDF + logistic regression, Claude Haiku | `frameworks bench-fetch`; `scripts/standard_benchmarks.py topics` (in `inference/`, see its docstring); `frameworks bench-llm --task topics --model <m>` |
| Entities | a seeded sample (2026) of 300 test sentences each from CoNLL-2003 (`en`) and CoNLL-2002 (`es`), PER/ORG/LOC | GLiNER as the pipeline runs it (its labels, threshold 0.50), `Davlan/xlm-roberta-base-ner-hrl`, spaCy small, Claude Haiku | `scripts/standard_benchmarks.py entities`; `frameworks bench-llm --task ner --model <m>` |

The deterministic models run in `inference/`'s environment (invariant 13);
spaCy rides along with `uv run --with`, so no pyproject changed. The CoNLL
text is licensed and gitignored (`data/evaluation/benchmarks/.gitignore`).

What they cannot say:

- **SIB-200's seven topics are not the pipeline's 23**, and its items are
  single sentences, not articles. It shows what training buys the method
  (untrained 0.75 -> trained 0.89-0.91), not how the app's classifier scores.
- **xlmr-ner was trained on CoNLL's training sets**; GLiNER and Claude never
  saw them. It is the supervised ceiling, not a like-for-like rival. spaCy's
  models were trained on other corpora with other conventions.
- **Claude may have read both test sets in training.** They are public and old.
- **GLiNER's labels are the pipeline's eight**, mapped onto three; its low
  English ORG score is partly CoNLL's sports tables, where a city names a team.
- **Entity timings are from a rerun beside Claude calls**; the first, idle
  run was faster (GLiNER 0.08 s, xlmr 0.03 s a sentence in English).
- One SIB-200 sentence was refused by Haiku's safety filter and is counted wrong.
- Two harness errors were found and fixed on the way: xlmr's output was split
  into sub-word pieces, then into single words. Its first two figures (0.76,
  0.56) were the harness's, not the model's.

## Resources and model size (2026-11-11)

Every comparison is read beside what the model needs: parameters, size on
disk, memory once loaded and at peak, cores used, and where it runs.
`resources.json`, drawn as the last table of `report.md`:

    cd inference && uv run --with ... python ../scripts/standard_benchmarks.py resources

(the `--with` lines of the script's docstring; Ollama must be up for its
models). Each local model is measured in a process of its own. Rerun it
when a model is added: a contender without its row is not comparable.
