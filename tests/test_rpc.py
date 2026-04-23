"""
Tests for RPC client.
"""

import pytest
from unittest.mock import patch, MagicMock

from ordex.rpc.client import RpcClient, RpcError


class TestRpcError:
    """Tests for RpcError exception."""

    def test_error_attributes(self):
        err = RpcError(-1, "Test error")
        assert err.code == -1
        assert err.message == "Test error"

    def test_error_string(self):
        err = RpcError(-1, "Test error")
        assert "RPC error -1" in str(err)
        assert "Test error" in str(err)


class TestRpcClient:
    """Tests for RpcClient."""

    def test_init_defaults(self):
        rpc = RpcClient()
        assert rpc.url == "http://127.0.0.1:25175"
        assert rpc.auth == ("rpcuser", "rpcpass")
        assert rpc.timeout == 30

    def test_init_custom(self):
        rpc = RpcClient(
            url="http://localhost:8332",
            username="user",
            password="pass",
            timeout=60,
        )
        assert rpc.url == "http://localhost:8332"
        assert rpc.auth == ("user", "pass")
        assert rpc.timeout == 60

    def test_call_method(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"blocks": 100}}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.call("getblockchaininfo")
            assert result == {"blocks": 100}

    def test_call_with_params(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "abc123"}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.call("getblockhash", 42)
            assert result == "abc123"
            mock_post.assert_called_once()

    def test_call_error_response(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"code": -32600, "message": "Invalid request"}, "result": None}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(RpcError) as exc_info:
                rpc.call("invalid")
            assert exc_info.value.code == -32600

    def test_call_network_error(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.side_effect = Exception("Connection error")
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(Exception):
                rpc.call("getblockchaininfo")

    def test_getattr(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": 123}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.getblockcount()
            assert result == 123


class TestConvenienceMethods:
    """Tests for convenience methods."""

    def test_getblockchaininfo(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": {"blocks": 100, "chain": "OXC"}}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.getblockchaininfo()
            assert result["blocks"] == 100

    def test_getblockcount(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": 1000}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.getblockcount()
            assert result == 1000

    def test_getblockhash(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "0000abc"}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.getblockhash(0)
            assert result == "0000abc"

    def test_getnewaddress(self):
        rpc = RpcClient()
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "oTEST123"}
        mock_response.raise_for_status = MagicMock()
        
        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_response
            result = rpc.getnewaddress()
            assert result == "oTEST123"