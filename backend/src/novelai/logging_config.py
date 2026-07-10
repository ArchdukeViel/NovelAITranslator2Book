"""Logging configuration and utilities for Novel AI.

This module is the canonical home for all logging setup, formatters, and
request/correlation ID tracking. It consolidates the former
``utils/logging.py`` and ``logging_config.py`` into a single module.

Call ``configure_logging()`` at startup (done by ``runtime/bootstrap.py``).
Use ``get_logger(__name__)`` in modules. Use ``set_request_id()`` /
``get_request_id()`` for request-scoped correlation.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

from novelai.config.settings import settings
from novelai.core.security import redact_secret_text, redact_sensitive

# ---------------------------------------------------------------------------
# Request/correlation ID tracking
# ---------------------------------------------------------------------------

_request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


def get_request_id() -> str | None:
    """Return the current request/correlation ID, or None if not set."""
    return _request_id_var.get()


def set_request_id(request_id: str | None = None) -> str:
    """Set a request/correlation ID for the current context.

    Args:
        request_id: Explicit ID to use, or None to auto-generate a UUID.

    Returns:
        The active request ID.
    """
    rid = request_id or uuid.uuid4().hex[:12]
    _request_id_var.set(rid)
    return rid


def clear_request_id() -> None:
    """Clear the current request/correlation ID."""
    _request_id_var.set(None)


class _RequestIdFilter(logging.Filter):
    """Inject the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_var.get()  # type: ignore[attr-defined]
        return True


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


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


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging with redaction.

    Suitable for production use with log aggregation tools. Includes
    request_id, module, function, and line info.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secret_text(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add request/correlation ID if present
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_data["request_id"] = request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = redact_secret_text(self.formatException(record.exc_info))

        # Add extra fields if present (e.g., from logger.info("msg", extra={"key": "value"}))
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            log_data.update(redact_sensitive(extra_fields))

        return json.dumps(log_data, ensure_ascii=False)


class SimpleFormatter(logging.Formatter):
    """Simple text formatter for development/console use."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",   # Green
        "WARNING": "\033[33m", # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m", # Red background
        "RESET": "\033[0m",
    }

    def format(self, record: logging.LogRecord) -> str:
        use_color = sys.stderr.isatty()

        levelname = record.levelname
        if use_color and levelname in self.COLORS:
            levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"

        # Format: [LEVEL] logger.name: message  (request_id if present)
        request_id = getattr(record, "request_id", None)
        rid_suffix = f" [{request_id}]" if request_id else ""
        msg = f"[{levelname}] {record.name}: {redact_secret_text(record.getMessage())}{rid_suffix}"
        if record.exc_info:
            msg += f"\n{redact_secret_text(self.formatException(record.exc_info))}"

        return msg


# ---------------------------------------------------------------------------
# Configuration functions
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure root logger. Reads LOG_FORMAT env var.

    LOG_FORMAT=json  -> JSON lines to stdout
    LOG_FORMAT=text or unset -> human-readable format to stdout
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


def setup_logging(
    log_level: str = "INFO",
    log_file: Path | None = None,
    use_json: bool = False,
) -> None:
    """Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file to write logs to
        use_json: Use JSON formatter (for production) vs text (for development)
    """
    # Parse level
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler (always write to stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.addFilter(_RequestIdFilter())
    formatter = StructuredFormatter() if use_json else SimpleFormatter()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.addFilter(_RequestIdFilter())
        file_formatter = StructuredFormatter()  # Always JSON for files
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific loggers
    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Enable Novel AI module logging
    logging.getLogger("novelai").setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def configure_from_settings() -> None:
    """Configure logging based on app settings."""
    log_level = settings.LOG_LEVEL.upper()
    log_dir = settings.DATA_DIR / "logs"
    log_file = log_dir / "novelai.log" if settings.ENV == "production" else None
    use_json = settings.ENV == "production"

    setup_logging(log_level=log_level, log_file=log_file, use_json=use_json)


# Initialize logging on module import
try:
    configure_from_settings()
except Exception:
    # Fallback if settings not available yet
    setup_logging(log_level="INFO")
    logging.getLogger(__name__).debug("Settings unavailable; using default logging config.")
