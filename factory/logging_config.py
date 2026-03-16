"""
factory/logging_config.py
--------------------------
Logging setup for the factory pipeline.

Call setup() once at process start — including in each worker process,
since multiprocessing.Pool children do not inherit the parent's logging config.

Usage:
    from factory.logging_config import setup
    setup()                        # default: logs/factory.log
    setup(log_dir="custom/logs")   # custom directory
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


_FMT = (
    "%(asctime)s "
    "[%(processName)s:%(process)d] "
    "%(levelname)-8s "
    "%(name)s "
    "— %(message)s"
)

_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class _BatchFilter(logging.Filter):
    """
    Injects batch_id into log records that don't have one.
    Allows formatters to always reference %(batch_id)s safely.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "batch_id"):
            record.batch_id = "-"
        return True


def setup(log_dir: str = "logs", level: int = logging.INFO) -> None:
    """
    Configure root logger with a rotating file handler and a stream handler.

    - File: logs/factory.log, rotates at 10 MB, keeps 5 backups.
    - Stream: stdout, same format.
    - Both handlers inject batch_id via _BatchFilter.

    Safe to call multiple times — handlers are not duplicated.

    Args:
        log_dir: Directory where factory.log is written. Created if missing.
        level:   Root logging level (default INFO).
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if root.handlers:
        return  # already configured in this process

    fmt = logging.Formatter(_FMT, datefmt=_DATE_FMT)
    batch_filter = _BatchFilter()

    # Rotating file handler — 10 MB per file, keep 5 backups
    file_handler = logging.handlers.RotatingFileHandler(
        filename     = f"{log_dir}/factory.log",
        maxBytes     = 10_000_000,
        backupCount  = 5,
        encoding     = "utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(batch_filter)

    # Stream handler — terminal output
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    stream_handler.addFilter(batch_filter)

    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


def get_logger(name: str, batch_id: int | None = None) -> logging.LoggerAdapter:
    """
    Return a LoggerAdapter that automatically injects batch_id into every record.

    Usage:
        logger = get_logger(__name__, batch_id=42)
        logger.info("item %s done", item_id)
        # → "... factory.runner — [batch=42] item 123 done"

    Args:
        name:     Logger name (typically __name__).
        batch_id: Current batch id, or None if not in a batch context.
    """
    base = logging.getLogger(name)
    extra = {"batch_id": batch_id if batch_id is not None else "-"}
    return logging.LoggerAdapter(base, extra)
