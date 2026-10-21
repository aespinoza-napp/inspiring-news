#!/usr/bin/env python3
"""
Time one verifier-shaped call against an Ollama server, with the time
spent reading the prompt and writing the answer reported apart.

Why apart: on a CPU the two cost differently and are fixed differently.
Reading the prompt is compute-bound - fewer prompt tokens, a GPU or an
integrated GPU help. Writing is memory-bound - fewer answer tokens, the
right thread count help. docs/decisions/performance.md has what this
measured on the dev laptop, 2026-10-21.

The prompt is the verifier's real system prompt and the shape of its
user prompt (an article block, a claim, N numbered sources of M
characters each) built from the committed samples in
backend/data/processed/. Ollama's native API, not the OpenAI one the
backend uses, because only the native one takes `options` (num_thread,
num_batch) and reports the two durations. Every call gets a fresh
prefix, so no call is answered from the previous one's prompt cache.

Usage (from backend/):

    uv run python ../scripts/bench_ollama.py --model llama3.2:3b
    uv run python ../scripts/bench_ollama.py --model llama3.2:3b --options '{"num_thread": 10}' --repeats 3
    uv run python ../scripts/bench_ollama.py --url http://localhost:11435 --model llama3.2:3b

Interleave two configurations (run them alternately, several times) on
a laptop: thermal throttling and background scans move a single
measurement by a factor of two.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from src.services.fact_checker.verification.llm_verification import SYSTEM_PROMPT  # noqa: E402

SAMPLES = "data/processed/*.json"


def user_prompt(sources: int, chars: int) -> str:

    articles = [json.loads(Path(path).read_text(encoding="utf-8")) for path in sorted(glob.glob(SAMPLES))]
    items = [(article.get("title") or "", article.get("url") or "", article.get("body") or "") for article in articles]
    items = items[:sources]

    block = "\n\n".join(f"[{i}] {title}\nURL: {url}\n{body[:chars]}" for i, (title, url, body) in enumerate(items))
    claim = items[0][2][:200].split(".")[0]

    # A fresh first line: the server must read the whole user prompt.
    return f"Run {uuid.uuid4().hex[:8]}.\nArticle the claim comes from:\nHeadline: {items[0][0]}\n\nClaim:\n{claim}\n\nEvidence:\n{block}"


def call(url: str, model: str, prompt: str, options: dict, timeout: float) -> dict:

    body = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        "options": {"temperature": 0, **options},
    }

    request = urllib.request.Request(f"{url}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})

    started = time.monotonic()
    answer = json.load(urllib.request.urlopen(request, timeout=timeout))
    wall = time.monotonic() - started

    prompt_s = answer.get("prompt_eval_duration", 0) / 1e9
    answer_s = answer.get("eval_duration", 0) / 1e9

    return {
        "wall_s": round(wall, 1),
        "load_s": round(answer.get("load_duration", 0) / 1e9, 1),
        "prompt_tokens": answer.get("prompt_eval_count"),
        "prompt_s": round(prompt_s, 1),
        "prompt_tok_s": round(answer.get("prompt_eval_count", 0) / prompt_s, 1) if prompt_s else None,
        "answer_tokens": answer.get("eval_count"),
        "answer_s": round(answer_s, 1),
        "answer_tok_s": round(answer.get("eval_count", 0) / answer_s, 1) if answer_s else None,
    }


def main() -> int:

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", default="http://localhost:11434", help="the Ollama server (default: localhost:11434)")
    parser.add_argument("--model", required=True)
    parser.add_argument("--options", default="{}", help='Ollama options as JSON, e.g. \'{"num_thread": 10}\'')
    parser.add_argument("--sources", type=int, default=3, help="evidence items in the prompt (default 3)")
    parser.add_argument("--chars", type=int, default=1500, help="characters of each (default 1500)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=900.0)
    args = parser.parse_args()

    options = json.loads(args.options)

    for _ in range(args.repeats):
        result = call(args.url, args.model, user_prompt(args.sources, args.chars), options, args.timeout)
        print(json.dumps({"model": args.model, "options": options, **result}), flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
