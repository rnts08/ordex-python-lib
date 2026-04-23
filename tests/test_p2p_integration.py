"""
Tests for CAddress serialization in P2P messages.
"""

import pytest
from io import BytesIO

from ordex.net.messages import CAddress
from ordex.chain.chainparams import oxc_mainnet
from ordex.net.sync import BlockSynchronizer, ChainState, PeerManager
from ordex.primitives.block import CBlockHeader
from ordex.core.hash import sha256d


class TestCAddressIPv4:
    """Tests for CAddress with IPv4 addresses."""

    def test_ipv4_address(self):
        addr = CAddress(
            services=1,
            ip=bytes([127, 0, 0, 1] + [0] * 12),
            port=8333,
            timestamp=1234567890,
        )
        data = addr.to_bytes()
        assert len(data) >= 26

    def test_ipv6_address(self):
        addr = CAddress(
            services=1,
            ip=bytes([0x20, 0x01, 0x0d, 0xb8] + [0] * 12),
            port=8333,
            timestamp=1234567890,
        )
        data = addr.to_bytes()
        assert len(data) >= 26

    def test_localhost(self):
        addr = CAddress(
            services=0,
            ip=bytes([127, 0, 0, 1] + [0] * 12),
            port=8333,
            timestamp=1234567890,
        )
        data = addr.to_bytes()
        restored = CAddress.deserialize(BytesIO(data))
        assert restored.port == 8333


class TestCAddressEdgeCases:
    """Edge case tests for CAddress."""

    def test_zero_port(self):
        addr = CAddress(
            services=0,
            ip=bytes(16),
            port=0,
            timestamp=1234567890,
        )
        data = addr.to_bytes()
        restored = CAddress.deserialize(BytesIO(data))
        assert restored.port == 0

    def test_max_port(self):
        addr = CAddress(
            services=0,
            ip=bytes(16),
            port=65535,
            timestamp=1234567890,
        )
        data = addr.to_bytes()
        restored = CAddress.deserialize(BytesIO(data))
        assert restored.port == 65535


class TestBlockSynchronizer:
    """Additional tests for BlockSynchronizer."""

    def test_sync_init(self):
        params = oxc_mainnet()

        class MockConn:
            def __init__(self):
                self.params = params
            async def send_message(self, *args):
                pass
            async def recv_message(self, *args):
                return ("headers", b"")

        sync = BlockSynchronizer(MockConn(), params)
        assert sync.params == params
        assert sync.state is not None

    def test_chain_state_height(self):
        params = oxc_mainnet()
        state = ChainState(params)

        header = CBlockHeader(
            version=1,
            hash_prev_block=bytes.fromhex("00" * 32),
            hash_merkle_root=bytes.fromhex("01" * 32),
            time=1234567890,
            bits=0x1e0ffff0,
            nonce=12345,
        )

        state.add_header(header)
        assert state.height == 1

        state.add_header(header)
        assert state.height == 1  # No increase for duplicate


class TestPeerManagerIntegration:
    """Integration tests for PeerManager."""

    def test_peer_manager_init(self):
        params = oxc_mainnet()
        pm = PeerManager(params)

        assert pm.connections == {}
        assert pm.peer_heights == {}
        assert pm.best_peer is None

    def test_peer_selection(self):
        params = oxc_mainnet()
        pm = PeerManager(params)

        pm.peer_heights = {
            "peer1:8333": 100,
            "peer2:8333": 500,
            "peer3:8333": 300,
        }
        pm._update_best_peer()

        assert pm.best_peer == "peer2:8333"