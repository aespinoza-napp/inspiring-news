# Build context is `backend/` (see docker-compose.yml), so every COPY
# path below is relative to the backend directory, not the repo root.

FROM python:3.12-slim

# Matches backend/.python-version and pyproject's requires-python, which
# are both 3.12. They used to disagree - pyproject claimed >=3.9 - and
# that disagreement is what made this build fail: resolving for 3.9 split
# the lock in two and handed 3.12 a torch that depends on cuda-toolkit.

# uv is the project's dependency manager (see CLAUDE.md); copied from
# its own published image rather than pip-installed, so the version is
# pinned and the layer is tiny.
#
# Pinned to match the uv that produced backend/uv.lock. The lockfile
# declares `revision = 2`, which older uv (0.5.x) cannot read - it fails
# the `uv sync --frozen` below outright. If you regenerate the lockfile
# with a newer uv, bump this tag too.
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /usr/local/bin/uv

# git: DataLakeRepository shells out to `git rev-parse --short HEAD` to
# stamp each stored record with the code revision that produced it. It
# degrades gracefully when git is missing, but then every record in the
# lake loses its code_revision - so install it and keep traceability.
# curl: for the healthcheck below.
RUN apt-get update \
    && apt-get install --no-install-recommends -y git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# UV_HTTP_TIMEOUT: torch is a ~200MB single wheel even CPU-only. uv's
# 30s default is a stall timeout rather than a total one, but it is
# tight enough on a slow connection to fail a build that would otherwise
# finish. Declared above the instruction, not inside it - a comment in
# the middle of a line continuation is a Dockerfile trap.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=180 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# src/ has no __init__.py anywhere - it is a namespace package throughout
# (see CLAUDE.md), and pyproject.toml declares no [build-system], so the
# app is never installed into the venv. It is imported from the working
# directory instead, exactly as `pythonpath = ["."]` does for pytest.
# Stated explicitly rather than relying on uvicorn happening to put the
# working directory on sys.path.
ENV PYTHONPATH=/app

# Dependencies first, in their own layer: this installs torch,
# transformers, sentence-transformers and friends - the slowest part of
# the build by a wide margin - and it only re-runs when pyproject.toml
# or uv.lock actually change, not on every source edit.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# The transformer models (GLiNER, the embedding model, the sentiment
# classifier) are NOT baked into the image - they download on first use,
# which is why docker-compose.yml mounts a named volume here. Without
# that volume every `docker compose up` re-downloads several GB.
ENV HF_HOME=/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD curl -fsS http://localhost:8000/docs > /dev/null || exit 1

# No --reload: that is a local-dev convenience (see container.py's note
# on reload re-paying model-loading cost), and it would re-import the
# world inside the container on every file event.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
