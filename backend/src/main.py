import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.config.settings import settings
from src.container import job_store
from src.services.job_journal import JobJournal

# Python's root logger defaults to WARNING, so plain logger.info() calls
# (e.g. src/services/job_runner.py's per-phase timing) would silently
# never print. INFO here makes that timing visible without touching
# uvicorn's own access/error logging (which configures itself).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attached at startup rather than built into the container: importing
    # the app (as the API tests do) must not start writing job journals
    # into the real lake. TestClient only runs this when used as a
    # context manager, which those tests do not do.
    if settings.LAKE_ENABLED:
        job_store.attach_journal(JobJournal(settings.LAKE_PATH / "journal"))

    yield


app = FastAPI(lifespan=lifespan)

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