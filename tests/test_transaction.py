"""
Tests for Transaction Service.
"""

import pytest

from ordex.rpc.transaction import (
    TransactionService,
    TransactionBuilder,
    TransactionBroadcaster,
    Transaction,
    TxInput,
    TxOutput,
    TxStatus,
    BroadcastResult,
)


class MockRpcClient:
    def __init__(self, broadcast_success=True, txid="mock_txid"):
        self._broadcast_success = broadcast_success
        self._txid = txid
        self._mempool = []

    def sendrawtransaction(self, raw_tx):
        if self._broadcast_success:
            return self._txid
        raise Exception("Broadcast failed")

    def getrawmempool(self, verbose=False):
        return self._mempool


class TestTxStatus:
    def test_statuses(self):
        assert TxStatus.DRAFT.value == "draft"
        assert TxStatus.SIGNED.value == "signed"
        assert TxStatus.BROADCAST.value == "broadcast"
        assert TxStatus.CONFIRMED.value == "confirmed"
        assert TxStatus.FAILED.value == "failed"


class TestTxInput:
    def test_to_dict(self):
        inp = TxInput(
            txid="abc123",
            vout=0,
            amount=100000,
            address="bc1q...",
        )
        data = inp.to_dict()
        assert data["txid"] == "abc123"
        assert data["amount"] == 100000


class TestTxOutput:
    def test_to_dict(self):
        out = TxOutput(
            address="bc1qxyz",
            amount=50000,
            is_change=False,
        )
        data = out.to_dict()
        assert data["address"] == "bc1qxyz"
        assert data["amount"] == 50000


class TestBroadcastResult:
    def test_to_dict(self):
        result = BroadcastResult(
            success=True,
            txid="abc123",
            timestamp="2024-01-01T00:00:00Z",
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["txid"] == "abc123"


class TestTransaction:
    def test_to_dict(self):
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            outputs=[TxOutput(address="bc1q", amount=90000)],
            fee=10000,
            fee_rate=10.0,
            status=TxStatus.DRAFT,
        )
        data = tx.to_dict()
        assert len(data["inputs"]) == 1
        assert len(data["outputs"]) == 1
        assert data["fee"] == 10000


class TestTransactionBuilder:
    def test_add_input(self):
        builder = TransactionBuilder()
        builder.add_input("txid1", 0, 100000, "addr1")
        assert len(builder.inputs) == 1
        assert builder.inputs[0].txid == "txid1"

    def test_add_output(self):
        builder = TransactionBuilder()
        builder.add_output("addr1", 50000)
        assert len(builder.outputs) == 1
        assert builder.outputs[0].amount == 50000

    def test_set_fee_rate(self):
        builder = TransactionBuilder()
        builder.set_fee_rate(15.0)
        assert builder.fee_rate == 15.0

    def test_set_change_address(self):
        builder = TransactionBuilder()
        builder.set_change_address("bc1qchange")
        assert builder.change_address == "bc1qchange"

    def test_calculate_fee(self):
        builder = TransactionBuilder()
        builder.set_fee_rate(10.0)
        fee = builder.calculate_fee(100, 400)
        assert fee == 1000

    def test_build(self):
        builder = TransactionBuilder()
        builder.add_input("txid1", 0, 100000)
        builder.add_output("addr1", 90000)
        builder.set_fee_rate(10.0)
        tx = builder.build()
        assert tx.status == TxStatus.DRAFT
        assert len(tx.inputs) == 1
        assert len(tx.outputs) == 1

    def test_build_with_change(self):
        builder = TransactionBuilder()
        builder.add_input("txid1", 0, 100000)
        builder.add_output("addr1", 50000)
        builder.set_fee_rate(10.0)
        builder.set_change_address("bc1qchange")
        tx = builder.build()
        assert len(tx.outputs) == 2
        change_out = next((o for o in tx.outputs if o.is_change), None)
        assert change_out is not None

    def test_build_empty(self):
        builder = TransactionBuilder()
        tx = builder.build()
        assert len(tx.inputs) == 0
        assert len(tx.outputs) == 0


class TestTransactionBroadcaster:
    def test_init(self):
        broadcaster = TransactionBroadcaster()
        assert broadcaster._rpc_client is None

    def test_set_rpc_client(self):
        broadcaster = TransactionBroadcaster()
        rpc = MockRpcClient()
        broadcaster.set_rpc_client(rpc)
        assert broadcaster._rpc_client is rpc

    def test_broadcast_no_client(self):
        broadcaster = TransactionBroadcaster()
        result = broadcaster.broadcast("raw_tx")
        assert result.success is False
        assert "No RPC client" in result.error

    def test_broadcast_success(self):
        rpc = MockRpcClient(broadcast_success=True, txid="tx123")
        broadcaster = TransactionBroadcaster(rpc_client=rpc)
        result = broadcaster.broadcast("raw_tx")
        assert result.success is True
        assert result.txid == "tx123"

    def test_broadcast_failure(self):
        rpc = MockRpcClient(broadcast_success=False)
        broadcaster = TransactionBroadcaster(rpc_client=rpc)
        result = broadcaster.broadcast("raw_tx")
        assert result.success is False

    def test_get_raw_mempool(self):
        rpc = MockRpcClient()
        rpc._mempool = ["tx1", "tx2", "tx3"]
        broadcaster = TransactionBroadcaster(rpc_client=rpc)
        mempool = broadcaster.get_raw_mempool()
        assert len(mempool) == 3


class TestTransactionService:
    def test_init(self):
        service = TransactionService()
        assert service._rpc_client is None

    def test_init_with_client(self):
        rpc = MockRpcClient()
        service = TransactionService(rpc_client=rpc)
        assert service._rpc_client is rpc

    def test_set_rpc_client(self):
        service = TransactionService()
        rpc = MockRpcClient()
        service.set_rpc_client(rpc)
        assert service._rpc_client is rpc

    def test_set_wallet_manager(self):
        service = TransactionService()
        service.set_wallet_manager("manager")
        assert service._wallet_manager == "manager"


class TestTransactionServiceBuild:
    def test_build_basic(self):
        service = TransactionService()
        tx = service.build("wallet1", [("addr1", 50000)], 10.0)
        assert tx.status == TxStatus.DRAFT
        assert len(tx.outputs) == 1

    def test_build_multiple_outputs(self):
        service = TransactionService()
        outputs = [("addr1", 10000), ("addr2", 20000), ("addr3", 30000)]
        tx = service.build("wallet1", outputs, 10.0)
        assert len(tx.outputs) == 3

    def test_build_with_fee_rate(self):
        service = TransactionService()
        tx = service.build("wallet1", [("addr1", 50000)], 15.0)
        assert tx.fee_rate == 15.0


class TestTransactionServiceSign:
    def test_sign(self):
        service = TransactionService()
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            outputs=[TxOutput(address="addr1", amount=90000)],
            status=TxStatus.DRAFT,
        )
        signed = service.sign(tx, "wallet1")
        assert signed.status == TxStatus.SIGNED
        assert len(signed.raw_tx) > 0


class TestTransactionServiceBroadcast:
    def test_broadcast_success(self):
        rpc = MockRpcClient(broadcast_success=True, txid="tx123")
        service = TransactionService(rpc_client=rpc)
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            outputs=[TxOutput(address="addr1", amount=90000)],
            status=TxStatus.SIGNED,
        )
        result = service.broadcast(tx)
        assert result.success is True
        assert result.txid == "tx123"

    def test_broadcast_unsigned(self):
        rpc = MockRpcClient()
        service = TransactionService(rpc_client=rpc)
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            status=TxStatus.DRAFT,
        )
        result = service.broadcast(tx)
        assert result.success is True

    def test_broadcast_failure(self):
        rpc = MockRpcClient(broadcast_success=False)
        service = TransactionService(rpc_client=rpc)
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            outputs=[TxOutput(address="addr1", amount=90000)],
            status=TxStatus.SIGNED,
        )
        result = service.broadcast(tx)
        assert result.success is False


class TestTransactionServiceReplace:
    def test_replace(self):
        rpc = MockRpcClient()
        service = TransactionService(rpc_client=rpc)
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            outputs=[TxOutput(address="addr1", amount=90000)],
            status=TxStatus.BROADCAST,
        )
        new_tx = service.replace("txid", 20.0)
        assert new_tx is None

    def test_replace_nonexistent(self):
        service = TransactionService()
        new_tx = service.replace("nonexistent", 20.0)
        assert new_tx is None


class TestTransactionServiceMonitor:
    def test_monitor(self):
        service = TransactionService()
        service.monitor("tx123", lambda conf: None)
        assert "tx123" in service._callbacks_confirmed

    def test_unmonitor(self):
        service = TransactionService()
        service.monitor("tx123", lambda conf: None)
        service.unmonitor("tx123")
        assert "tx123" not in service._callbacks_confirmed

    def test_notify_confirmation(self):
        service = TransactionService()
        results = []
        service.monitor("tx123", lambda conf: results.append(conf))
        service.notify_confirmation("tx123", 1)
        assert len(results) == 1
        assert results[0] == 1


class TestTransactionServiceCallbacks:
    def test_on_broadcast(self):
        service = TransactionService()
        results = []
        service.on_broadcast(lambda txid: results.append(txid))
        tx = Transaction(
            inputs=[],
            outputs=[TxOutput(address="addr1", amount=50000)],
            status=TxStatus.SIGNED,
            raw_tx="raw_data",
        )
        rpc = MockRpcClient()
        service.set_rpc_client(rpc)
        service.broadcast(tx)
        assert len(results) == 1


class TestTransactionServiceGet:
    def test_get_transaction(self):
        service = TransactionService()
        tx = Transaction(
            inputs=[TxInput(txid="abc", vout=0, amount=100000)],
            status=TxStatus.SIGNED,
            txid="tx123",
        )
        with service._lock:
            service._transactions["tx123"] = tx
        result = service.get_transaction("tx123")
        assert result is not None
        assert result.txid == "tx123"

    def test_get_transaction_none(self):
        service = TransactionService()
        result = service.get_transaction("nonexistent")
        assert result is None

    def test_get_confirmations_not_found(self):
        service = TransactionService()
        count = service.get_confirmations("nonexistent")
        assert count == 0

    def test_get_confirmations_confirmed(self):
        service = TransactionService()
        tx = Transaction(status=TxStatus.CONFIRMED)
        with service._lock:
            service._transactions["tx123"] = tx
        count = service.get_confirmations("tx123")
        assert count == 6

    def test_is_in_mempool(self):
        rpc = MockRpcClient()
        rpc._mempool = ["tx1", "tx2"]
        service = TransactionService(rpc_client=rpc)
        assert service.is_in_mempool("tx1") is True
        assert service.is_in_mempool("tx3") is False