"""Logging configuration and utilities for Novel AI.

Provides structured logging with appropriate levels for different concerns.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from novelai.config.settings import settings


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging.
    
    Suitable for production use with log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present (e.g., from logger.info("msg", extra={"key": "value"}))
        extra_fields = getattr(record, "extra_fields", None)
        if isinstance(extra_fields, dict):
            log_data.update(extra_fields)

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

        # Format: [LEVEL] logger.name: message (function:line)
        msg = f"[{levelname}] {record.name}: {record.getMessage()}"
        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
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
    formatter = StructuredFormatter() if use_json else SimpleFormatter()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
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
