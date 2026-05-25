"""Structured JSON logging configuration.

Call ``configure_logging()`` once at application startup (in ``main.py``).
After that, use the standard ``logging`` module throughout the codebase —
all output will be emitted as newline-delimited JSON to stdout.
"""
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    # Fields that are always present in the standard LogRecord but that we
    # don't want to duplicate inside the ``extra`` envelope.
    _SKIP_ATTRS: frozenset[str] = frozenset(
        {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        # Build the core payload.
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Attach exception info when present.
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "value": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Attach any extra fields passed via ``logging.getLogger().info(..., extra={...})``.
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in self._SKIP_ATTRS and not k.startswith("_")
        }
        if extra:
            payload["extra"] = extra

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger to emit structured JSON to stdout.

    This should be called exactly once, before the FastAPI application
    starts accepting requests.

    Args:
        level: Minimum log level string (e.g. ``"DEBUG"``, ``"INFO"``).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any handlers that may have been added by third-party libraries
    # before our configuration runs.
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root_logger.addHandler(handler)

    # Silence overly verbose third-party loggers.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
