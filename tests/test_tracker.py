"""
Tests for Transaction Tracker Service.
"""

import pytest

from ordex.rpc.tracker import (
    TxTracker,
    WalletTracker,
    TxTrackingInfo,
    BalanceDelta,
    TxHistoryEntry,
    ConfirmationLevel,
)


class MockRpcClient:
    def __init__(self, mempool=None):
        self._mempool = mempool or []

    def getrawmempool(self, verbose=False):
        return self._mempool


class TestConfirmationLevel:
    def test_levels(self):
        assert ConfirmationLevel.ZERO_CONF.value == 0
        assert ConfirmationLevel.ONE_CONF.value == 1
        assert ConfirmationLevel.SIX_CONF.value == 6


class TestTxTrackingInfo:
    def test_to_dict(self):
        info = TxTrackingInfo(
            txid="abc123",
            wallet_id="wallet1",
            amount=100000,
            fee=1000,
            status="pending",
            confirmations=0,
        )
        data = info.to_dict()
        assert data["txid"] == "abc123"
        assert data["wallet_id"] == "wallet1"
        assert data["amount"] == 100000


class TestBalanceDelta:
    def test_to_dict(self):
        delta = BalanceDelta(
            wallet_id="wallet1",
            txid="tx123",
            old_balance=1000000,
            new_balance=900000,
            delta=-100000,
        )
        data = delta.to_dict()
        assert data["wallet_id"] == "wallet1"
        assert data["delta"] == -100000


class TestTxHistoryEntry:
    def test_to_dict(self):
        entry = TxHistoryEntry(
            txid="tx123",
            wallet_id="wallet1",
            amount=50000,
            fee=500,
            confirmations=1,
            timestamp="2024-01-01T00:00:00Z",
            block_height=100,
        )
        data = entry.to_dict()
        assert data["txid"] == "tx123"
        assert data["block_height"] == 100


class TestTxTracker:
    def test_init(self):
        tracker = TxTracker()
        assert tracker._rpc_client is None
        assert tracker.get_tracked_count() == 0

    def test_set_rpc_client(self):
        tracker = TxTracker()
        rpc = MockRpcClient()
        tracker.set_rpc_client(rpc)
        assert tracker._rpc_client is rpc

    def test_set_block_service(self):
        tracker = TxTracker()
        tracker.set_block_service("block_service")
        assert tracker._block_service == "block_service"


class TestTxTrackerTracking:
    def test_track(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000, fee=1000)
        info = tracker.get_status("tx123")
        assert info is not None
        assert info.txid == "tx123"
        assert info.amount == 100000

    def test_track_with_metadata(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000, metadata={"note": "test"})
        info = tracker.get_status("tx123")
        assert info.metadata["note"] == "test"

    def test_untrack(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        assert tracker.untrack("tx123") is True
        assert tracker.get_status("tx123") is None

    def test_untrack_not_tracked(self):
        tracker = TxTracker()
        assert tracker.untrack("nonexistent") is False


class TestTxTrackerStatus:
    def test_get_status(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        info = tracker.get_status("tx123")
        assert info is not None
        assert info.wallet_id == "wallet1"

    def test_get_status_not_found(self):
        tracker = TxTracker()
        info = tracker.get_status("nonexistent")
        assert info is None

    def test_get_confirmations_not_tracked(self):
        tracker = TxTracker()
        count = tracker.get_confirmations("nonexistent")
        assert count == 0


class TestTxTrackerConfirmations:
    def test_update_confirmations(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        tracker.update_confirmations("tx123", 1)
        info = tracker.get_status("tx123")
        assert info.confirmations == 1

    def test_update_confirmations_with_block(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        tracker.update_confirmations("tx123", 1, block_hash="abc123", block_height=100)
        info = tracker.get_status("tx123")
        assert info.block_hash == "abc123"
        assert info.block_height == 100

    def test_mark_confirmed(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        tracker.mark_confirmed("tx123", "block123", 100)
        info = tracker.get_status("tx123")
        assert info.status == "confirmed"
        assert info.confirmations >= 1


class TestTxTrackerRBF:
    def test_mark_replaced(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        tracker.track("tx456", "wallet1", 100000)
        tracker.mark_replaced("tx123", "tx456")
        info = tracker.get_status("tx123")
        assert info.status == "replaced"
        assert info.replaced_by == "tx456"

    def test_mark_replaced_updates_replacement(self):
        tracker = TxTracker()
        tracker.track("tx123", "wallet1", 100000)
        tracker.track("tx456", "wallet1", 100000)
        tracker.mark_replaced("tx123", "tx456")
        replacement = tracker.get_status("tx456")
        assert replacement.replaces == "tx123"


class TestTxTrackerCallbacks:
    def test_on_zero_conf(self):
        tracker = TxTracker()
        results = []
        tracker.on_zero_conf(lambda txid, info: results.append((txid, info)))
        tracker.track("tx123", "wallet1", 100000)
        tracker.update_confirmations("tx123", 1)
        assert len(results) == 1

    def test_on_one_conf(self):
        tracker = TxTracker()
        results = []
        tracker.on_one_conf(lambda txid, info: results.append((txid, info)))
        tracker.track("tx123", "wallet1", 100000)
        tracker.update_confirmations("tx123", 1)
        assert len(results) == 1

    def test_on_six_conf(self):
        tracker = TxTracker()
        results = []
        tracker.on_six_conf(lambda txid, info: results.append((txid, info)))
        tracker.on_confirmation(lambda txid, info: results.append((txid, info)))
        tracker.track("tx123", "wallet1", 100000)
        tracker.update_confirmations("tx123", 6)
        assert len(results) >= 1

    def test_on_confirmation(self):
        tracker = TxTracker()
        results = []
        tracker.on_confirmation(lambda txid, info: results.append((txid, info)))
        tracker.track("tx123", "wallet1", 100000)
        tracker.mark_confirmed("tx123", "block123", 100)
        assert len(results) == 1

    def test_on_replaced(self):
        tracker = TxTracker()
        results = []
        tracker.on_replaced(lambda txid, info: results.append((txid, info)))
        tracker.track("tx123", "wallet1", 100000)
        tracker.track("tx456", "wallet1", 100000)
        tracker.mark_replaced("tx123", "tx456")
        assert len(results) == 1

    def test_callback_exception_handling(self):
        tracker = TxTracker()

        def failing_callback(txid, info):
            raise ValueError("Test error")

        tracker.on_confirmation(failing_callback)
        tracker.track("tx123", "wallet1", 100000)
        tracker.mark_confirmed("tx123", "block123", 100)


class TestTxTrackerQueries:
    def test_get_pending(self):
        tracker = TxTracker()
        tracker.track("tx1", "wallet1", 100000)
        tracker.track("tx2", "wallet1", 100000)
        tracker.mark_confirmed("tx1", "block", 100)
        pending = tracker.get_pending("wallet1")
        assert len(pending) == 1
        assert pending[0].txid == "tx2"

    def test_get_confirmed(self):
        tracker = TxTracker()
        tracker.track("tx1", "wallet1", 100000)
        tracker.track("tx2", "wallet1", 100000)
        tracker.mark_confirmed("tx1", "block", 100)
        confirmed = tracker.get_confirmed("wallet1")
        assert len(confirmed) == 1
        assert confirmed[0].txid == "tx1"

    def test_get_pending_no_wallet(self):
        tracker = TxTracker()
        pending = tracker.get_pending("nonexistent")
        assert len(pending) == 0


class TestTxTrackerMempool:
    def test_scan_mempool_no_rpc(self):
        tracker = TxTracker()
        result = tracker.scan_mempool()
        assert result["found"] == 0

    def test_scan_mempool(self):
        rpc = MockRpcClient(mempool=["tx1", "tx2"])
        tracker = TxTracker(rpc_client=rpc)
        tracker.track("tx1", "wallet1", 100000)
        tracker.track("tx2", "wallet1", 100000)
        tracker.track("tx3", "wallet1", 100000)
        result = tracker.scan_mempool()
        assert result["found"] == 2


class TestWalletTracker:
    def test_init(self):
        tracker = WalletTracker()
        assert tracker._rpc_client is None

    def test_set_rpc_client(self):
        tracker = WalletTracker()
        rpc = MockRpcClient()
        tracker.set_rpc_client(rpc)
        assert tracker._rpc_client is rpc

    def test_track_balance(self):
        tracker = WalletTracker()
        tracker.track_balance("wallet1", 1000000)
        balance = tracker.get_balance("wallet1")
        assert balance == 1000000

    def test_track_balance_change(self):
        tracker = WalletTracker()
        tracker.track_balance("wallet1", 1000000)
        tracker.track_balance("wallet1", 900000)
        balance = tracker.get_balance("wallet1")
        assert balance == 900000

    def test_get_history(self):
        tracker = WalletTracker()
        tracker.track_balance("wallet1", 1000000)
        tracker.track_balance("wallet1", 900000)
        history = tracker.get_history("wallet1")
        assert len(history) == 2

    def test_get_history_limit(self):
        tracker = WalletTracker()
        for i in range(10):
            tracker.track_balance("wallet1", i * 100000)
        history = tracker.get_history("wallet1", limit=5)
        assert len(history) == 5

    def test_on_balance_change(self):
        tracker = WalletTracker()
        results = []
        tracker.on_balance_change("wallet1", lambda delta: results.append(delta))
        tracker.track_balance("wallet1", 1000000)
        tracker.track_balance("wallet1", 900000)
        assert len(results) == 2