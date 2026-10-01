"""
The process's logging: human-readable lines by default, one JSON object
per line with LOG_FORMAT=json (what docker-compose.prod.yml sets).

JSON because the job runner's phase timings are the most useful thing
this process logs, and as prose ("enriched (+8.50s, total 9.52s)") a log
shipper has to regex them back into numbers. As JSON they arrive as
fields: `phase`, `step_seconds`, `total_seconds`, `job`, `url`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

# Everything a LogRecord carries by itself. Whatever else is on a record
# came from `extra=` and is written out as a field.
_RECORD_ATTRIBUTES = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}

TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# uvicorn installs its own handlers on these before it imports the app,
# so they would keep writing text beside the JSON. In JSON mode they hand
# their records to the root handler instead.
UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


class JsonFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:

        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in vars(record).items():
            if key not in _RECORD_ATTRIBUTES and not key.startswith("_"):
                entry[key] = value

        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False, default=str)


def configure_logging(log_format: str) -> None:
    """
    INFO and up to stderr, as text or JSON. Python's root logger defaults
    to WARNING, so without this the job runner's logger.info() timing
    lines would never print.
    """

    if log_format != "json":
        logging.basicConfig(level=logging.INFO, format=TEXT_FORMAT)
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    for name in UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
