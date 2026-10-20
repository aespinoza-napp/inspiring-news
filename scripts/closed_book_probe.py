#!/usr/bin/env python3
"""
The verifier's model with no evidence at all: what it says about a claim
from its training alone.

    cd backend
    LLM_TIMEOUT=180 uv run python ../scripts/closed_book_probe.py \
        data/evaluation/xfact_en_es_pilot.jsonl llama3.2:3b \
        data/evaluation/reports/xfact_en_es_pilot/closed_book_llama3.2-3b.json

Two questions it answers (docs/decisions/xfact-comparison.md):

- **Does the model remember the fact-check?** Every x-fact claim was
  checked and published by 2021, and llama3.2's pretraining data runs to
  December 2023 (Meta's model card), so the verdict pages may be in its
  weights. If the model gets the gold label from the claim alone well
  above the majority rate, the pipeline's accuracy cannot be credited to
  the evidence it retrieved.
- **The analogue of X-Fact's Claim-Only baseline.** Gupta & Srikumar's
  Table 3 reports a model given the claim text alone. This is the same
  input, to a zero-shot model instead of a fine-tuned one.

The same client the pipeline uses (`LLMClient`, temperature, JSON mode,
the JSON retry), the same five verdicts with the same definitions as
`LLMVerifier`'s prompt, and nothing else: no evidence, no claimant, no
date, no fact-checker named. One claim at a time.

Before the harness had a closed-book mode (`cli run --closed-book`, whose
records pair with every other run's), this was the only way to ask; kept
because the x-fact reports cite its JSON. A diagnostic, run once per set,
its output kept beside the run's report. Scored with the harness's own metrics and
bootstrap (`src/evaluation/metrics.py`), so its numbers mean what the
report's mean.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from src.config.settings import settings  # noqa: E402
from src.evaluation import metrics  # noqa: E402
from src.evaluation.dataset import load_dataset  # noqa: E402
from src.services.llms import LLMClient, LLMUnavailableError  # noqa: E402

# The prompt and the verdicts live in the harness since its closed-book
# mode (src/evaluation/closed_book.py, 2026-10-20): one prompt, so the
# probe's numbers and a closed-book run's mean the same thing.
from src.evaluation.closed_book import SYSTEM_PROMPT, VERDICTS  # noqa: E402


def ask(client: LLMClient, claim: str) -> dict:

    started = time.perf_counter()

    try:
        answer = client.complete_json(SYSTEM_PROMPT, f"Claim: {claim}")
    except LLMUnavailableError as exc:
        return {"status": "unreachable", "error": str(exc)[:200], "seconds": time.perf_counter() - started}

    seconds = round(time.perf_counter() - started, 3)

    if not isinstance(answer, dict):
        return {"status": "invalid", "verdict": "UNVERIFIED", "seconds": seconds}

    verdict = str(answer.get("verdict", "")).strip().upper()

    return {
        "status": "ok" if verdict in VERDICTS else "invalid",
        # An answer outside the five is scored as the UNVERIFIED the
        # pipeline would have made of it (LLMVerifier's fallback).
        "verdict": verdict if verdict in VERDICTS else "UNVERIFIED",
        "confidence": answer.get("confidence"),
        "recallsFactCheck": answer.get("recalls_fact_check") is True,
        "factChecker": str(answer.get("fact_checker") or "")[:80],
        "explanation": str(answer.get("explanation") or "")[:400],
        "seconds": seconds,
    }


def scored(pairs: list[tuple[str, str]]) -> dict:

    if not pairs:
        return {"n": 0}

    result = metrics.classification(pairs)
    intervals = metrics.bootstrap(sorted(pairs))

    return {
        "n": result["n"],
        "accuracy": result["accuracy"],
        "accuracyCI": intervals.get("accuracy"),
        "macroF1": result["macroF1"],
        "macroF1CI": intervals.get("macroF1"),
        "coverage": result["coverage"],
        "selectiveAccuracy": result["selectiveAccuracy"],
        "goldClasses": result["goldClasses"],
        "confusion": result["confusion"],
    }


def main() -> int:

    if len(sys.argv) != 4:
        print(__doc__)
        return 2

    dataset = load_dataset(sys.argv[1])
    model = sys.argv[2]
    target = Path(sys.argv[3])

    client = LLMClient(model=model)

    rows = []

    for index, row in enumerate(dataset.rows, start=1):
        answer = ask(client, row.claim)
        rows.append({"id": row.id, "language": row.language, "label": row.label, **answer})
        print(f"{index:>4}/{len(dataset.rows)} {row.id} gold={row.label:<14} said={answer.get('verdict')}", flush=True)

    answered = [row for row in rows if row["status"] != "unreachable"]

    report = {
        "dataset": {"path": str(dataset.path), "sha256": dataset.sha256, "rows": len(dataset.rows)},
        "model": model,
        "llmBaseUrl": settings.LLM_BASE_URL,
        "ranAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "systemPrompt": SYSTEM_PROMPT,
        "unreachable": [row["id"] for row in rows if row["status"] == "unreachable"],
        "invalid": sum(1 for row in rows if row["status"] == "invalid"),
        "recallsFactCheck": sum(1 for row in answered if row.get("recallsFactCheck")),
        "all": scored([(row["label"], row["verdict"]) for row in answered]),
        "byLanguage": {
            language: scored([(row["label"], row["verdict"]) for row in answered if row["language"] == language])
            for language in sorted({row["language"] for row in answered})
        },
        "claims": rows,
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps({key: report[key] for key in report if key not in ("claims", "systemPrompt")}, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
