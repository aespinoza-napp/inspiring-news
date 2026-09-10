# Build context is `inference/` (see docker-compose.yml), mirroring
# docker/backend.Dockerfile's shape exactly - same base image, same uv
# pin, same two-layer sync, same CPU-torch rationale. This service still
# does not download models eagerly at build time (see HF_HOME below) -
# it downloads them once at container startup and caches them in the
# model-cache volume, same as backend used to.

FROM python:3.12-slim

# Matches inference/.python-version and pyproject's requires-python.
COPY --from=ghcr.io/astral-sh/uv:0.7.2 /uv /usr/local/bin/uv

# curl: for the HEALTHCHECK below. No git needed here - unlike backend,
# nothing in this service stamps a code revision.
RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# UV_HTTP_TIMEOUT: same reasoning as backend.Dockerfile - torch is a
# large single wheel even CPU-only, and uv's 30s default is a stall
# timeout tight enough to fail a build that would otherwise finish.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=180 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# src/ has no __init__.py - same namespace-package convention as
# backend/src, imported from the working directory rather than
# installed.
ENV PYTHONPATH=/app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# GLiNER, the sentiment classifier and the sentence-transformer download
# on first use - several GB combined. Cached in the model-cache volume
# (moved here from backend in this same change) so that cost is paid
# once, not on every container start.
ENV HF_HOME=/models

EXPOSE 8001

# start-period is long, and measured rather than guessed: a genuinely
# cold model-cache volume - all three models downloading from scratch,
# BAAI/bge-m3 alone is ~2.2GB - took ~11 minutes to report healthy in
# testing. This matches docker-compose.yml's override for the same
# reason: a container reported unhealthy before start-period elapses is
# a failed dependency to anything waiting on it, not just a slow one.
HEALTHCHECK --interval=10s --timeout=5s --start-period=900s --retries=5 \
    CMD curl -fsS http://localhost:8001/healthz > /dev/null || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
