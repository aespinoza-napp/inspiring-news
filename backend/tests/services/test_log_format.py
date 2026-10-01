import json
import logging

import pytest

from src.services.log_format import UVICORN_LOGGERS, JsonFormatter, configure_logging


def record(**extra) -> logging.LogRecord:
    entry = logging.makeLogRecord({
        "name": "src.services.job_runner",
        "levelname": "INFO",
        "levelno": logging.INFO,
        "msg": "[analyze %s] %s",
        "args": ("3c546a3d", "enriched"),
    })
    for key, value in extra.items():
        setattr(entry, key, value)
    return entry


def test_a_line_is_one_json_object_with_the_message_formatted():

    line = JsonFormatter().format(record())

    entry = json.loads(line)
    assert "\n" not in line
    assert entry["message"] == "[analyze 3c546a3d] enriched"
    assert entry["level"] == "INFO"
    assert entry["logger"] == "src.services.job_runner"
    assert entry["time"].endswith("+00:00")


def test_extra_fields_become_keys():
    """What makes the phase timings readable by a log shipper without a regex."""

    entry = json.loads(JsonFormatter().format(
        record(phase="enriched", step_seconds=8.5, total_seconds=9.52, job="3c546a3d")
    ))

    assert entry["phase"] == "enriched"
    assert entry["step_seconds"] == 8.5
    assert entry["total_seconds"] == 9.52
    assert entry["job"] == "3c546a3d"


def test_the_record_s_own_attributes_are_not_repeated_as_fields():

    entry = json.loads(JsonFormatter().format(record()))

    assert set(entry) == {"time", "level", "logger", "message"}


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    uvicorn = {
        name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate)
        for name in UVICORN_LOGGERS
    }
    yield
    root.handlers, root.level = saved[0], saved[1]
    for name, (handlers, propagate) in uvicorn.items():
        logging.getLogger(name).handlers = handlers
        logging.getLogger(name).propagate = propagate


def test_json_mode_routes_uvicorn_through_the_same_handler(restore_logging):
    """Otherwise its access lines stay text, interleaved with the JSON."""

    logging.getLogger("uvicorn.access").addHandler(logging.NullHandler())
    logging.getLogger("uvicorn.access").propagate = False

    configure_logging("json")

    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)

    for name in UVICORN_LOGGERS:
        assert logging.getLogger(name).handlers == []
        assert logging.getLogger(name).propagate is True
