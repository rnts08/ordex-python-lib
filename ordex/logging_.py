"""
Logging configuration for ordex library.

Provides standardized logging setup for applications using the library.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional


DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: int = logging.INFO,
    format: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    handler: Optional[logging.Handler] = None,
    library_levels: Optional[dict[str, int]] = None,
) -> None:
    """Configure logging for the ordex library.

    Args:
        level: Default logging level for the root logger
        format: Log message format
        date_format: Date/time format
        handler: Optional custom handler (defaults to StreamHandler)
        library_levels: Optional dict of {module: level} for fine-grained control
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if handler is None:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)

    formatter = logging.Formatter(format, datefmt=date_format)
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    if library_levels:
        for module, mod_level in library_levels.items():
            logging.getLogger(module).setLevel(mod_level)
    else:
        logging.getLogger("ordex").setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_library_level(level: int, name: str = "ordex") -> None:
    """Set the logging level for the library.

    Args:
        level: Logging level (e.g., logging.DEBUG, logging.INFO)
        name: Logger name prefix
    """
    logging.getLogger(name).setLevel(level)


class LogCapture:
    """Context manager for capturing log messages in tests.

    Usage:
        with LogCapture() as capture:
            do_something()
            assert "error message" in capture.output
    """

    def __init__(self, level: int = logging.WARNING, logger: str = "ordex"):
        self.level = level
        self.logger_name = logger
        self.handler: Optional[logging.Handler] = None
        self.output: list[str] = []

    def __enter__(self) -> "LogCapture":
        self.handler = logging.Handler()
        self.handler.setLevel(self.level)
        self.handler.emit = lambda record: self.output.append(
            self.handler.format(record)
        )
        logging.getLogger(self.logger_name).addHandler(self.handler)
        return self

    def __exit__(self, *args) -> None:
        if self.handler:
            logging.getLogger(self.logger_name).removeHandler(self.handler)


class OrdexLogger(logging.Logger):
    """Custom logger with additional helpers."""

    def trace(self, message: str, *args, **kwargs) -> None:
        """Log a trace message."""
        self.log(5, message, *args, **kwargs)

    def debug_short(self, message: str, **kwargs) -> None:
        """Log a short debug message."""
        if self.isEnabledFor(logging.DEBUG):
            self.debug(message, stacklevel=2, **kwargs)


logging.setLoggerClass(OrdexLogger)


def configure_from_env() -> None:
    """Configure logging from environment variables.

    Environment variables:
        ORDEX_LOG_LEVEL: DEBUG, INFO, WARNING, ERROR, CRITICAL
        ORDEX_LOG_FORMAT: Custom format string
    """
    import os

    level_str = os.environ.get("ORDEX_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    log_format = os.environ.get("ORDEX_LOG_FORMAT", DEFAULT_FORMAT)

    setup_logging(level=level, format=log_format)