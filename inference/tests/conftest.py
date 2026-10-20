"""
The inference suite loads the real models, and the native thread pools
behind them (torch's, and onnxruntime's, which GLiNER pulls in) can abort
the interpreter while it shuts down: "terminate called without an active
exception", exit 134, after every test has passed. Reproduced 2026-10-20
on the dev machine (torch 2.14.0+cpu, onnxruntime 1.29.0): 2 of 3 runs
of `uv run pytest -q` ended so, the third exited 0, the same 13 tests
passing every time - and `./scripts/check.sh`, the definition of done,
reported the suite as failed.

So once pytest has reported everything, the process leaves with pytest's
own exit status, skipping the destructors that abort. Nothing is lost:
the models hold no state worth writing, and the report is already out.
"""

import os
import sys

import pytest


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):

    status = getattr(config, "_inference_exitstatus", None)

    if status is None:
        return

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(int(status))


def pytest_sessionfinish(session, exitstatus):

    # Kept for pytest_unconfigure, which runs after the terminal summary
    # and has no exit status of its own.
    session.config._inference_exitstatus = exitstatus
