"""
Tests for Mempool Service.
"""

import pytest

from ordex.rpc.mempool import (
    MempoolService,
    FeeEstimateMode,
    FeeEstimate,
    MempoolStats,
    TrackedTransaction,
)


class MockRpcClient:
    def __init__(self, mempool_data=None, fee_estimate=20.0):
        self._mempool_data = mempool_data or {}
        self._fee_estimate = fee_estimate

    def getrawmempool(self, verbose=True):
        return self._mempool_data

    def estimatesmartfee(self, conf_target):
        return {"feerate": self._fee_estimate, "errors": []}


class TestFeeEstimate:
    def test_to_dict(self):
        estimate = FeeEstimate(
            mode=FeeEstimateMode.ECONOMIC,
            feerate=15.5,
            blocks=6,
            timestamp="2024-01-01T00:00:00Z",
        )
        data = estimate.to_dict()
        assert data["mode"] == "economic"
        assert data["feerate"] == 15.5
        assert data["blocks"] == 6


class TestMempoolStats:
    def test_to_dict(self):
        stats = MempoolStats(
            size_bytes=1000000,
            transaction_count=5000,
            fee_percentiles=[5.0, 10.0, 15.0, 20.0, 25.0],
            min_fee=2.0,
            max_fee=100.0,
            avg_fee=12.5,
        )
        data = stats.to_dict()
        assert data["size_bytes"] == 1000000
        assert data["transaction_count"] == 5000
        assert len(data["fee_percentiles"]) == 5


class TestTrackedTransaction:
    def test_to_dict(self):
        tx = TrackedTransaction(
            txid="abc123",
            added_at="2024-01-01T00:00:00Z",
            size_bytes=500,
            fee=0.001,
            fee_rate=200.0,
            status="pending",
        )
        data = tx.to_dict()
        assert data["txid"] == "abc123"
        assert data["status"] == "pending"
        assert data["fee_rate"] == 200.0


class TestMempoolService:
    def test_init(self):
        service = MempoolService()
        assert service._rpc_client is None
        assert service.get_tracked_count() == 0

    def test_init_with_rpc_client(self):
        rpc = MockRpcClient()
        service = MempoolService(rpc_client=rpc)
        assert service._rpc_client is rpc

    def test_set_rpc_client(self):
        service = MempoolService()
        rpc = MockRpcClient()
        service.set_rpc_client(rpc)
        assert service._rpc_client is rpc


class TestMempoolServiceMempool:
    def test_get_mempool_empty(self):
        service = MempoolService()
        mempool = service.get_mempool()
        assert mempool == []

    def test_get_mempool_with_rpc(self):
        rpc = MockRpcClient({
            "tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []},
            "tx2": {"size": 300, "fee": 0.0005, "feerate": 1.67, "time": 1001, "height": 100, "depends": [], "spent": []},
        })
        service = MempoolService(rpc_client=rpc)
        mempool = service.get_mempool()
        assert len(mempool) == 2
        assert mempool[0]["txid"] == "tx1"

    def test_get_mempool_cache(self):
        rpc = MockRpcClient({"tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []}})
        service = MempoolService(rpc_client=rpc)
        service.get_mempool()
        service.get_mempool()
        assert service._mempool_cache is not None

    def test_get_mempool_refresh(self):
        rpc = MockRpcClient({"tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []}})
        service = MempoolService(rpc_client=rpc)
        service.get_mempool()
        rpc._mempool_data = {"tx2": {"size": 600, "fee": 0.002, "feerate": 3.33, "time": 1001, "height": 100, "depends": [], "spent": []}}
        mempool = service.get_mempool(refresh=True)
        assert len(mempool) == 1
        assert mempool[0]["txid"] == "tx2"


class TestMempoolServiceStats:
    def test_get_stats_empty(self):
        service = MempoolService()
        stats = service.get_stats()
        assert stats.transaction_count == 0
        assert stats.size_bytes == 0

    def test_get_stats_with_data(self):
        rpc = MockRpcClient({
            "tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []},
            "tx2": {"size": 300, "fee": 0.0005, "feerate": 1.67, "time": 1001, "height": 100, "depends": [], "spent": []},
        })
        service = MempoolService(rpc_client=rpc)
        stats = service.get_stats()
        assert stats.transaction_count == 2
        assert stats.size_bytes == 800
        assert stats.min_fee == 1.67
        assert stats.max_fee == 2.0


class TestMempoolServiceFees:
    def test_get_fees_economic_no_rpc(self):
        service = MempoolService()
        estimate = service.get_fees(FeeEstimateMode.ECONOMIC)
        assert estimate.mode == FeeEstimateMode.ECONOMIC
        assert estimate.feerate == 10.0
        assert estimate.blocks == 6

    def test_get_fees_half_hour_no_rpc(self):
        service = MempoolService()
        estimate = service.get_fees(FeeEstimateMode.HALF_HOUR)
        assert estimate.mode == FeeEstimateMode.HALF_HOUR
        assert estimate.feerate == 20.0
        assert estimate.blocks == 3

    def test_get_fees_hour_no_rpc(self):
        service = MempoolService()
        estimate = service.get_fees(FeeEstimateMode.HOUR)
        assert estimate.mode == FeeEstimateMode.HOUR
        assert estimate.feerate == 50.0
        assert estimate.blocks == 1

    def test_get_fees_with_rpc(self):
        rpc = MockRpcClient(fee_estimate=25.0)
        service = MempoolService(rpc_client=rpc)
        estimate = service.get_fees(FeeEstimateMode.ECONOMIC)
        assert estimate.feerate == 25.0


class TestMempoolServiceUTXOs:
    def test_get_utxos_empty(self):
        service = MempoolService()
        utxos = service.get_utxos()
        assert len(utxos) == 0

    def test_get_utxos_with_mempool(self):
        rpc = MockRpcClient({
            "tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []},
        })
        service = MempoolService(rpc_client=rpc)
        utxos = service.get_utxos()
        assert len(utxos) == 1
        assert utxos[0]["txid"] == "tx1"


class TestMempoolServiceTracking:
    def test_track_transaction(self):
        service = MempoolService()
        service.track_transaction("tx123", size_bytes=500, fee=0.001)
        assert service.get_tracked_count() == 1
        tx = service.get_transaction("tx123")
        assert tx is not None
        assert tx["txid"] == "tx123"
        assert tx["status"] == "pending"

    def test_track_transaction_with_metadata(self):
        service = MempoolService()
        service.track_transaction("tx123", metadata={"wallet_id": "wallet1", "address": "bc1q..."})
        tx = service.get_transaction("tx123")
        assert tx["metadata"]["wallet_id"] == "wallet1"

    def test_untrack_transaction(self):
        service = MempoolService()
        service.track_transaction("tx123")
        assert service.untrack_transaction("tx123") is True
        assert service.get_tracked_count() == 0

    def test_untrack_nonexistent(self):
        service = MempoolService()
        assert service.untrack_transaction("nonexistent") is False

    def test_get_pending_transactions(self):
        service = MempoolService()
        service.track_transaction("tx1", fee=0.001, size_bytes=100)
        service.track_transaction("tx2", fee=0.002, size_bytes=200)
        pending = service.get_pending_transactions()
        assert len(pending) == 2

    def test_mark_confirmed(self):
        service = MempoolService()
        service.track_transaction("tx123")
        service.mark_confirmed("tx123", "block_hash_abc")
        tx = service.get_transaction("tx123")
        assert tx["status"] == "confirmed"
        assert tx["block_hash"] == "block_hash_abc"
        assert tx["confirmations"] == 1


class TestMempoolServiceCallbacks:
    def test_on_new_transaction(self):
        service = MempoolService()
        results = []
        service.on_new_transaction(lambda txid: results.append(txid))
        diff = service.check_mempool_diff()
        assert "added" in diff

    def test_on_transaction_confirmed(self):
        service = MempoolService()
        results = []
        service.on_transaction_confirmed(lambda txid, block: results.append((txid, block)))
        service.track_transaction("tx123")
        service.mark_confirmed("tx123", "block_abc")
        assert len(results) == 1
        assert results[0] == ("tx123", "block_abc")

    def test_on_transaction_removed(self):
        service = MempoolService()
        results = []
        service.on_transaction_removed(lambda txid: results.append(txid))
        service.track_transaction("tx123")
        service.check_mempool_diff()
        assert len(results) == 1
        assert "tx123" in results

    def test_callback_exception_handling(self):
        service = MempoolService()

        def failing_callback(txid, block_hash):
            raise ValueError("Test error")

        service.on_transaction_confirmed(failing_callback)
        service.track_transaction("tx123")
        service.mark_confirmed("tx123", "block_abc")


class TestMempoolServiceCache:
    def test_clear_cache(self):
        rpc = MockRpcClient({"tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []}})
        service = MempoolService(rpc_client=rpc)
        service.get_mempool()
        assert service._mempool_cache is not None
        service.clear_cache()
        assert service._mempool_cache is None


class TestMempoolServiceCheckDiff:
    def test_check_mempool_diff_empty(self):
        service = MempoolService()
        diff = service.check_mempool_diff()
        assert "added" in diff
        assert "removed" in diff

    def test_check_mempool_diff_detects_changes(self):
        rpc = MockRpcClient({
            "tx1": {"size": 500, "fee": 0.001, "feerate": 2.0, "time": 1000, "height": 100, "depends": [], "spent": []},
        })
        service = MempoolService(rpc_client=rpc)
        service.track_transaction("tx1")
        diff = service.check_mempool_diff()
        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0


class TestFeeEstimateMode:
    def test_modes(self):
        assert FeeEstimateMode.ECONOMIC.value == "economic"
        assert FeeEstimateMode.HALF_HOUR.value == "half_hour"
        assert FeeEstimateMode.HOUR.value == "hour"