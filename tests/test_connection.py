"""
Tests for async node connection.
"""

import pytest
from unittest.mock import MagicMock

from ordex.net.connection import NodeConnection
from ordex.chain.chainparams import ChainParams


class TestNodeConnection:
    """Tests for NodeConnection."""

    def test_init(self):
        params = MagicMock(spec=ChainParams)
        conn = NodeConnection("127.0.0.1", 25174, params)
        assert conn.host == "127.0.0.1"
        assert conn.port == 25174
        assert conn.params == params
        assert conn.peer_version is None

    def test_init_defaults(self):
        params = MagicMock(spec=ChainParams)
        conn = NodeConnection("127.0.0.1", 25174, params)
        assert conn._connected is False
        assert conn.reader is None
        assert conn.writer is None


class TestConnectionLogging:
    """Tests for connection logging."""

    def test_logger_exists(self):
        from ordex.net.connection import logger
        assert logger is not None
        assert logger.name == "ordex.net.connection"