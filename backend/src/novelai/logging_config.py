"""JSON log formatter and log config helpers."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Emit log records as JSON lines.

    Fields: timestamp, level, logger, message, plus any extras set on the record.
    """

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge extra fields from record.__dict__ (set via `extra={...}`)
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text", "filename",
                "funcName", "levelname", "levelno", "lineno", "message", "module",
                "msecs", "msg", "name", "pathname", "process", "processName",
                "relativeCreated", "stack_info", "thread", "threadName",
            ):
                obj[key] = value
        if record.exc_info and record.exc_info[1]:
            obj["exception"] = str(record.exc_info[1])
        return json.dumps(obj, default=str)


def configure_logging() -> None:
    """Configure root logger. Reads LOG_FORMAT env var.

    LOG_FORMAT=json  → JSON lines to stdout
    LOG_FORMAT=text or unset → human-readable format to stdout
    """
    log_format = os.getenv("LOG_FORMAT", "text").strip().lower()
    handler = logging.StreamHandler()

    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove default handlers, add ours
    for h in root.handlers[:]:
        root.removeHandler(h)
    root.addHandler(handler)
