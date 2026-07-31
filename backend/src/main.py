import logging

from fastapi import FastAPI

from src.api.routes import router

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