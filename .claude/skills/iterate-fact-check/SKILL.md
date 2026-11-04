---
name: iterate-fact-check
description: One iteration of an agent's campaign to make the fact-checker more accurate and faster (thresholds, verifier prompts, what is searched, the verifier model), each try pre-registered and decided by a fixed rule on the train half. Use when asked to iterate on, tune or optimise fact-checking, to start or continue a campaign, or when run by /loop /iterate-fact-check <campaign>.
---

# One iteration of the fact-checking campaign

The loop is `cli iterate` (`backend/src/evaluation/iterate.py`); this skill is the agent
that drives it. Each invocation does **one step**: decide a finished run, start a pending
one, or propose the next try. Run it as `/loop /iterate-fact-check <campaign>`.

The rule is in the campaign's `rule.md`, written by `init`. **Never edit it, `split.json`,
the labels, or the campaign's `campaign.json` / `ledger.jsonl` by hand.** A rule edited
mid-campaign stops the campaign: the result must not choose its own criterion. The
`fact-check-change` skill holds the general rules. This one is the procedure.

All commands run from `backend/`. `CLI=uv run python -m src.evaluation.cli`.

## 0. Starting a campaign (once, only when asked)

```bash
$CLI iterate init --name <yyyymmdd-topic> \
  --evidence data/evaluation/runs/manual-train/llama3.2-3b-bench/cc053417c0cb \
  --goal "<one line from the user>"            # --tries 15 --screen 20 --target-median 20 --target-p90 30
git switch -c iterate/<name>                  # code tries are committed here, never on dev
```

`cc053417c0cb` is the one local searched train run with `evidence.jsonl` (29 Oct,
`llama3.2:3b-bench`, per-source verifier). While the campaign is active,
`.claude/hooks/sealed_test_half.py` refuses anything touching the test half.

## 1. Where are we?

```bash
$CLI iterate status --campaign <name>
```

- **STOP** printed: go to step 6.
- A try **pending** or **continue**: step 4 or 5.
- Otherwise: step 2.

The services a run needs (check them before starting one, and say what is missing rather
than starting a run that will fail):

| | Replay | Searched |
|---|---|---|
| `inference/` on :8001 (`cd inference && uv run uvicorn src.main:app --port 8001`); compose does not publish it | yes | yes |
| Ollama with the try's model (`ollama list`), and nothing else loaded (`ollama ps`, `ollama stop <other>`) | yes | yes |
| SearXNG on :8080 (`cd docker && docker compose up -d searxng`), and its source health | - | yes |

Keep the machine otherwise idle during a run: the seconds are part of the result.

## 2. Choose the next try

Read before choosing, newest first:

1. `status` and the ledger's `changed` lists (gained and lost claims of each try).
2. The baseline's report, from the `report` path in its ledger line: the **Stage
   attribution**, **Confidently wrong** ids and **Response time** sections.
3. The records of 3-5 wrong train claims in the baseline's `results.jsonl`: the stances,
   quotes, cited indices, `rawVerdict` vs `verdict`. A verdict is only as good as the
   stage before it. Work upstream (the `debug-verdict` skill).

Then pick **one** change with a reason found in those records, not a hunch. Prefer, in
order:

- **Replay over searched.** A replay is exact. A searched try has to beat a 6-9 point
  web noise.
- **Time first while the target is unmet.** The model is ~80% of a claim. Each source
  is one call under `per_source`, and a claim also waits for the other claim's call
  (`llmWait`).
- **Changes that leave old behaviour reachable** (a new `Literal` value or field, the
  default unchanged).

### What may change

**Replayed** (after retrieval, `PipelineThresholds` in `src/config/thresholds.py`). Write
the overrides to `<campaign dir>/tries/NN.json`:

| Lever | What is known |
|---|---|
| `max_evidence_per_claim` (down only; the evidence run fetched 5) | fewer sources = fewer per-source calls; `fast.json` uses 3 |
| `verifier_excerpt` / `verifier_excerpt_chars` | prompt length is model time; `fast.json` uses 400 chars |
| `ranking_text: passages` | ranking 6 s -> 0.7 s in the 22 Oct contest |
| `verifier_answer`: `per_source` (default), `full`, `compact` | per_source: natural claims 49 -> 67% on test, altered claims 60 -> 13%. compact: half the tokens |
| `verifier_rules: stated` | V1, not adopted alone |
| `evidence_min_pertinence`, `min_evidence_for_verdict`, `min_independent_domains`, `evidence_independence` | the gate trades confidently wrong for UNVERIFIED |

**Model** (`--kind model --model <m>`; a replay). Measured verifiers
(`docs/decisions/evaluation.md`, "Choosing the models", "The benchmark of 29 October"):

| Model | Known |
|---|---|
| `llama3.2:3b-bench` | the baseline, 7.2 s a call |
| `granite3.3:8b-bench` | +5.0 [-10, +20] on 20 claims, coverage 95%, kappa +0.27; 19.9 s a call. The one worth all 69 |
| `qwen3.5:9b-bench` | V5: best kappa, catches altered claims, but ~123 s a claim. Only with fewer, shorter sources |
| `gemma4:e4b-bench`, `qwen3.5:4b-bench` | -10 on 20 claims; not without a new reason |

**Hosted, for the benchmark** (`--kind model --provider groq --model <groq id>`; a
replay). The author **prefers self-hosted**. Groq is the comparison side, and it has usage
limits. Its key is `LLM_API_KEY` in `backend/.env`, never printed. Run hosted tries only
after the self-hosted tries of the same thresholds, so each pair compares like with like.
On 30 Oct, 5 replayed claims each (too few to rank them): `qwen/qwen3.8-27b` 4 right,
1.3 s a call; `openai/gpt-oss-120b` and `openai/gpt-oss-20b` 3 right, 2.5-3 s. A 429
waits out `retry-after`; a claim still throttled is set apart (`llmUnreachable`). If more
than one is set apart, the rule calls the try invalid. Re-run it with
`--retry-unavailable` once the limit resets, then score again.

**Prompt / code after retrieval** (`--kind prompt` or `code`): `verification/per_source.py`
(`PER_SOURCE_SYSTEM_PROMPT`), `verification/llm_verification.py`, `confidence_scorer.py`,
`ranking/ranking_retrieval.py`, `independence.py`, `FactChecker._judge`. Add the variant
behind a new threshold value (default unchanged), with a test. Run `./scripts/check.sh
fast` and the touched tests, then commit on `iterate/<name>` as `Iterate <name> try NN:
<what>` before `propose` (it refuses uncommitted code).

**Searched** (`--kind search`, or any of these, which `propose` detects by itself):
`query_kinds`, `evidence_fetch_candidates`, `evidence_prerank: lexical`,
`fetch_evidence_pages`, `claim_restatement: standalone`, `second_look_enabled`,
`claim_deadline_seconds`, raising `max_evidence_per_claim`, and code in
`fact_checker/retrieval/`, `terms.py`, `restatement.py`, `second_look.py`,
`services/scraper/`, `services/search.py`. The first searched try also makes the two
searched baselines (`propose` prints them). Run them back to back with the try.

### The order for campaign 20261104-speed (the author's choice, 4 Nov)

The baseline on this laptop: ~93 s a claim replayed (ranking 22 s, waiting for the other
claim's call 21 s, the model 48 s over ~5 calls and ~2,100 prompt tokens), plus ~15 s of
original retrieval. Self-hosted first, then the same on Groq:

1. `ranking_text: passages` (ranking time).
2. That, with `max_evidence_per_claim: 3` and `verifier_excerpt_chars: 400` (model time).
3. The best kept of those on the integrated GPU. The author runs `sudo
   ./scripts/ollama_igpu.sh on` first. It is the same model, so propose with `--again`
   and say "integrated GPU" in the hypothesis.
4. The best self-hosted thresholds on Groq, one model per try: `qwen/qwen3.8-27b`, then
   `openai/gpt-oss-120b`.
5. Granite 8B only with fewer, shorter sources: alone it took 227 s a claim here.

Revise the order when a result says so, and say why in the next hypothesis.

### Already measured: do not repeat without a new reason

- `fast` / `fast_snippets` (14-18 s a claim) cost ~17 points on the 69 (list verifier, 22 Oct).
- V4, quote first + "a different detail contradicts": same accuracy, more confidently wrong.
- Checking a supporting quote's figures by unit: would change about one verdict.
- The second look: +2.9 on train, +0.0 on test, off.
- Ollama thread counts: no setting beat the default on this CPU.
- Concurrency settings are not levers (invariant 12). The campaign runs every try under
  the evidence run's settings, so the seconds compare.

## 3. Propose it, before running anything

```bash
$CLI iterate propose --campaign <name> --kind <thresholds|prompt|model|code|search> \
  --hypothesis "<what is wrong, in which claims, and why this fixes it>" \
  --predict "<which claims should change, and the expected accuracy and seconds>" \
  [--thresholds <campaign dir>/tries/NN.json] [--model <m>]
```

It prints the commands: the screen (`--limit 20`), then the full run. They carry the
evidence run's settings.

## 4. Run it, in the background

Start the printed command with `run_in_background: true`. A replayed claim takes
~15-90 s, so a screen takes minutes and a full run up to an hour. Then end the turn. In
`/loop`, schedule a fallback wakeup of ~1800 s. The finished command re-invokes you.
**Never start a second run while one is going**: they would share the CPU and both
would have wrong seconds.

## 5. Score it

```bash
$CLI iterate score --campaign <name> --try N --run <the "run" directory the command printed>
```

- `continue`: the screen passed. Start the same command without `--limit` (it resumes),
  then score again.
- `screened-out`, `reject`, `invalid`: for a code try, `git revert --no-edit <its commit>`
  so the next try starts from the baseline's code.
- `keep`: leave the commit. A later try may **combine** kept ones, as a try of its own.
  Every try is judged against the baseline, never against another try.

Then write 2-4 lines to the user: the hypothesis, the decision and its numbers (accuracy
paired difference with interval, confidently wrong, median/p90 seconds), and which
claims it gained or lost. Say plainly when a result is "no detectable difference".

## 6. Stop

When `status` says STOP (a kept try meets the target, or the tries are spent), or the user
asks:

```bash
$CLI iterate close --campaign <name> --reason "<why>"
```

This writes `summary.md` and `benchmark.md` (every try side by side, self-hosted against
hosted: accuracy, interval, confidently wrong, seconds, calls, tokens, cost).
`$CLI iterate benchmark --campaign <name>` writes the table at any time. In `/loop`,
end the loop. Tell the user:

- the best kept try, with its train numbers;
- the trade-off: the best self-hosted against the best hosted, in accuracy, seconds, cost
  and what leaves the machine;
- the caveats: 69 claims, labels mostly the AI pass's, the evidence from 29 Oct (before
  the 3 Nov search change);
- that it goes to the **test half once, run by them**. Nothing becomes a default until
  then.

If they adopt it, the `fact-check-change` skill's "Recording it" applies.
