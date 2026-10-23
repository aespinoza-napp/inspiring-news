"""
Laya: typed decisions about a text, for whatever asks.

Laya (Apache-2.0, `convaiinnovations/laya`) answers `choice`, `score`
and `noul` questions in one forward pass and generates nothing. Like the
other three models here it knows nothing of what the questions mean: the
backend sends the state and the questions (backend/src/config/decisions.py)
and decides what an answer does. docs/decisions/laya.md.

Unlike them it is not loaded at start-up and not part of /healthz: the
pipeline runs without it unless a run switches a decision to it, and a
checkpoint is ~1.3 GB in memory. A checkpoint loads on its first request
and stays; at most DECISION_MAX_LOADED stay, least recently used first out.

    uv run python -m src.decisions predict --checkpoint <name> \
        --data <cases.jsonl> --out <predictions.jsonl>

answers a JSONL of cases (the format laya-train reads) without the
server, for the evaluation (backend/src/evaluation/decisions.py).
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from collections import OrderedDict
from logging import getLogger
from pathlib import Path
from typing import Any

from .config import settings

logger = getLogger(__name__)

# Laya's published checkpoints, by the names laya-train's --base takes.
BUILT_IN = {
    "english": ("convaiinnovations/laya", None),
    "multilingual": ("convaiinnovations/laya", "multilingual"),
    "typed-decisions": ("convaiinnovations/laya", "typed-decisions"),
}


class UnknownCheckpoint(LookupError):
    pass


def checkpoint_dir(name: str) -> Path | None:
    """A fine-tuned checkpoint's folder, or None for a built-in name.

    Only a plain folder name under DECISION_CHECKPOINTS_DIR: a request
    never names a path, so it cannot make this process read anywhere else.
    """

    if name in BUILT_IN:
        return None
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise UnknownCheckpoint(name)
    folder = Path(settings.DECISION_CHECKPOINTS_DIR) / name
    if not (folder / "rl_agent_config.json").is_file():
        raise UnknownCheckpoint(name)
    return folder


class DecisionModels:

    def __init__(self, max_loaded: int) -> None:
        self._max_loaded = max(1, max_loaded)
        self._agents: OrderedDict[str, Any] = OrderedDict()
        # One lock for loading and predicting: Laya's agent is not
        # documented as thread-safe (its own skill says to guard predict),
        # and on a CPU two forward passes at once are not faster than one
        # after the other.
        self._lock = threading.Lock()

    def loaded(self) -> list[str]:
        return list(self._agents)

    def _agent(self, name: str):
        if name in self._agents:
            self._agents.move_to_end(name)
            return self._agents[name]

        folder = checkpoint_dir(name)

        import laya  # imported here so the service starts without loading torch twice

        started = time.perf_counter()
        if folder is None:
            repo, subfolder = BUILT_IN[name]
            agent = laya.load(repo, subfolder=subfolder, device=settings.DECISION_DEVICE)
        else:
            agent = laya.load(str(folder), device=settings.DECISION_DEVICE)
        logger.info("Loaded decision checkpoint %s in %.1f s", name, time.perf_counter() - started)

        self._agents[name] = agent
        while len(self._agents) > self._max_loaded:
            evicted, _ = self._agents.popitem(last=False)
            logger.info("Unloaded decision checkpoint %s", evicted)
        return agent

    def predict(self, name: str, state: Any, questions: dict) -> dict:
        with self._lock:
            return self._agent(name).predict(state, questions)

    def predict_many(self, name: str, states: list[Any], questions: dict) -> list[dict]:
        """The same questions over many states, in input order."""

        with self._lock:
            agent = self._agent(name)
            return agent.predict_batch(states, questions, batch_size=settings.DECISION_BATCH_SIZE)


decision_models = DecisionModels(settings.DECISION_MAX_LOADED)


def _predict_file(name: str, data: Path, out: Path) -> None:
    cases = [json.loads(line) for line in data.read_text(encoding="utf-8").splitlines() if line.strip()]
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with out.open("w", encoding="utf-8", newline="\n") as f:
        for case in cases:
            t = time.perf_counter()
            result = decision_models.predict(name, case["state"], case["questions"])
            f.write(json.dumps({
                "meta": case.get("meta"),
                "expected": case.get("expected"),
                "answers": result["answers"],
                "seconds": round(time.perf_counter() - t, 4),
            }, ensure_ascii=False) + "\n")
    print(f"{len(cases)} cases answered by {name} in {time.perf_counter() - started:.1f} s -> {out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m src.decisions")
    sub = parser.add_subparsers(dest="command", required=True)
    predict = sub.add_parser("predict", help="answer a JSONL of cases with one checkpoint")
    predict.add_argument("--checkpoint", required=True,
                         help="a built-in name (multilingual, english) or a folder under DECISION_CHECKPOINTS_DIR")
    predict.add_argument("--data", type=Path, required=True)
    predict.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    _predict_file(args.checkpoint, args.data, args.out)


if __name__ == "__main__":
    main()
