"""
Tests for logging configuration.
"""

import logging
import pytest

from ordex.logging_ import (
    setup_logging, get_logger, set_library_level,
    LogCapture, OrdexLogger, configure_from_env,
    DEFAULT_FORMAT,
)


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_creates_handler(self):
        setup_logging(level=logging.DEBUG)
        root = logging.getLogger()
        assert len(root.handlers) > 0

    def test_setup_logging_sets_root_level(self):
        setup_logging(level=logging.WARNING)
        root = logging.getLogger()
        assert root.level == logging.WARNING


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        logger = get_logger("ordex.test")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_name(self):
        logger = get_logger("ordex.my_module")
        assert logger.name == "ordex.my_module"


class TestSetLibraryLevel:
    """Tests for set_library_level function."""

    def test_set_library_level(self):
        set_library_level(logging.ERROR)
        logger = logging.getLogger("ordex")
        assert logger.level == logging.ERROR


class TestLogCapture:
    """Tests for LogCapture context manager."""

    def test_capture_context_manager(self):
        with LogCapture() as capture:
            logger = logging.getLogger("ordex.test_capture")
            logger.warning("test message")
        
        assert isinstance(capture.output, list)


class TestConfigureFromEnv:
    """Tests for configure_from_env function."""

    def test_configure_from_env_default(self, monkeypatch):
        monkeypatch.delenv("ORDEX_LOG_LEVEL", raising=False)
        configure_from_env()
        logger = logging.getLogger("ordex")
        assert logger.level in [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]


class TestOrdexLogger:
    """Tests for OrdexLogger custom class."""

    def test_logger_has_trace(self):
        logger = logging.getLogger("ordex.trace_test")
        assert hasattr(logger, 'trace')

    def test_logger_has_debug_short(self):
        logger = logging.getLogger("ordex.debug_test")
        assert hasattr(logger, 'debug_short')