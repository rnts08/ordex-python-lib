"""
Tests for P2P block synchronization.
"""

import pytest

from ordex.chain.chainparams import oxc_mainnet
from ordex.net.sync import ChainState, BlockSynchronizer, PeerManager
from ordex.primitives.block import CBlockHeader
from ordex.core.hash import sha256d


class TestChainState:
    """Tests for ChainState class."""

    def test_add_header(self):
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

        added = state.add_header(header)
        assert added is True
        assert state.tip is not None
        assert state.height == 1

    def test_duplicate_header(self):
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
        added = state.add_header(header)
        assert added is False

    def test_get_locator_empty(self):
        params = oxc_mainnet()
        state = ChainState(params)

        locator = state.get_locator()
        assert len(locator) == 1
        assert locator[0] == bytes.fromhex("00" * 32)

    def test_get_locator_with_headers(self):
        params = oxc_mainnet()
        state = ChainState(params)

        prev_hash = bytes.fromhex("00" * 32)
        for i in range(5):
            header = CBlockHeader(
                version=1,
                hash_prev_block=prev_hash,
                hash_merkle_root=bytes([i] * 32),
                time=1234567890 + i,
                bits=0x1e0ffff0,
                nonce=i,
            )
            state.add_header(header)
            prev_hash = sha256d(header.to_bytes())

        locator = state.get_locator()
        assert len(locator) > 0
        assert locator[-1] == bytes.fromhex("00" * 32)

    def test_find_gap_no_gap(self):
        params = oxc_mainnet()
        state = ChainState(params)

        prev_hash = bytes.fromhex("00" * 32)
        for i in range(3):
            header = CBlockHeader(
                version=1,
                hash_prev_block=prev_hash,
                hash_merkle_root=bytes([i] * 32),
                time=1234567890 + i,
                bits=0x1e0ffff0,
                nonce=i,
            )
            state.add_header(header)
            prev_hash = sha256d(header.to_bytes())

        new_headers = [
            CBlockHeader(
                version=1,
                hash_prev_block=prev_hash,
                hash_merkle_root=bytes([i] * 32),
                time=1234567900 + i,
                bits=0x1e0ffff0,
                nonce=100 + i,
            )
            for i in range(2)
        ]

        gap = state.find_gap(new_headers)
        assert gap is None

    def test_find_gap_with_gap(self):
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

        new_headers = [
            CBlockHeader(
                version=1,
                hash_prev_block=bytes.fromhex("ff" * 32),
                hash_merkle_root=bytes([i] * 32),
                time=1234567900 + i,
                bits=0x1e0ffff0,
                nonce=100 + i,
            )
            for i in range(2)
        ]

        gap = state.find_gap(new_headers)
        assert gap == 0


class TestPeerManager:
    """Tests for PeerManager class."""

    def test_init(self):
        params = oxc_mainnet()
        manager = PeerManager(params)

        assert manager.params == params
        assert len(manager.connections) == 0
        assert manager.best_peer is None

    def test_update_best_peer(self):
        params = oxc_mainnet()
        manager = PeerManager(params)

        manager.peer_heights = {
            "192.168.1.1:8333": 100,
            "192.168.1.2:8333": 200,
            "192.168.1.3:8333": 150,
        }

        manager._update_best_peer()
        assert manager.best_peer == "192.168.1.2:8333"

    def test_update_best_peer_empty(self):
        params = oxc_mainnet()
        manager = PeerManager(params)

        manager._update_best_peer()
        assert manager.best_peer is None