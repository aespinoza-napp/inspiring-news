import logging

from fastapi import FastAPI

from src.api.routes import router
from src.config.settings import settings

# Python's root logger defaults to WARNING, so plain logger.info() calls
# (e.g. src/services/job_runner.py's per-phase timing) would silently
# never print. INFO here makes that timing visible without touching
# uvicorn's own access/error logging (which configures itself).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI()

app.include_router(router)

logger = logging.getLogger(__name__)

# Both of these are safe defaults for localhost and unsafe anywhere else,
# so say so at startup rather than letting the choice be silent.
if settings.STORAGE_API_KEY is None:
    logger.warning(
        "STORAGE_API_KEY is not set: /storage/* is open to anyone who can "
        "reach this process, and returns full article bodies and lineage. "
        "Set it before exposing this beyond localhost."
    )

if not settings.URL_GUARD_ENABLED:
    logger.warning(
        "URL_GUARD_ENABLED is false: this service will fetch any URL it is "
        "given, including private and link-local addresses."
    )