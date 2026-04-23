"""
Tests for UTXO Service.
"""

import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ordex.wallet.utxo import (
    UTXO, CoinSelector, CoinSelectionResult, CoinSelectionStrategy,
    Wallet, WalletStats, WalletManager,
)


class TestUTXO:
    """Tests for UTXO dataclass."""

    def test_create_utxo(self):
        utxo = UTXO(
            txid="abc123",
            vout=0,
            amount=100000,
            script_pubkey="76a914...",
        )
        assert utxo.txid == "abc123"
        assert utxo.vout == 0
        assert utxo.amount == 100000

    def test_outpoint(self):
        utxo = UTXO(txid="abc", vout=5, amount=1000, script_pubkey="")
        assert utxo.outpoint == ("abc", 5)

    def test_is_spendable(self):
        utxo = UTXO(
            txid="abc", vout=0, amount=1000, script_pubkey="",
            confirmations=6, coinbase=False,
        )
        assert utxo.is_spendable is True

    def test_coinbase_maturity(self):
        utxo_mature = UTXO(
            txid="abc", vout=0, amount=1000, script_pubkey="",
            confirmations=100, coinbase=True,
        )
        assert utxo_mature.is_spendable is True

        utxo_immature = UTXO(
            txid="abc", vout=0, amount=1000, script_pubkey="",
            confirmations=50, coinbase=True,
        )
        assert utxo_immature.is_spendable is False

    def test_to_dict(self):
        utxo = UTXO(txid="abc", vout=0, amount=1000, script_pubkey="OP_DUP")
        d = utxo.to_dict()
        assert d["txid"] == "abc"
        assert d["vout"] == 0
        assert d["amount"] == 1000

    def test_from_rpc(self):
        data = {
            "txid": "abc123",
            "vout": 1,
            "amount": "0.001",
            "scriptPubKey": "76a914...",
            "confirmations": 6,
            "address": "XvX26g...",
        }
        utxo = UTXO.from_rpc(data)
        assert utxo.txid == "abc123"
        assert utxo.vout == 1
        assert utxo.amount == 100000
        assert utxo.confirmations == 6


class TestCoinSelector:
    """Tests for CoinSelector."""

    def test_greedy_select(self):
        selector = CoinSelector(strategy=CoinSelectionStrategy.GREEDY)
        utxos = [
            UTXO(txid=f"tx{i}", vout=0, amount=amt, script_pubkey="", confirmations=6)
            for i, amt in enumerate([50000, 100000, 200000])
        ]

        result = selector.select(utxos, 150000, fee_per_byte=1)

        assert result.success is True
        assert result.total_amount >= 150000
        assert len(result.utxos) >= 1

    def test_optimized_select(self):
        selector = CoinSelector(strategy=CoinSelectionStrategy.OPTIMIZED)
        utxos = [
            UTXO(txid=f"tx{i}", vout=0, amount=amt, script_pubkey="", confirmations=6)
            for i, amt in enumerate([50000, 100000, 200000])
        ]

        result = selector.select(utxos, 150000, fee_per_byte=1)

        assert result.success is True
        assert result.excess < 100000

    def test_insufficient_funds(self):
        selector = CoinSelector()
        utxos = [
            UTXO(txid="tx1", vout=0, amount=1000, script_pubkey="", confirmations=6)
        ]

        result = selector.select(utxos, 10000, fee_per_byte=1)

        assert result.success is False
        assert result.error is not None

    def test_no_spendable_utxos(self):
        selector = CoinSelector()
        utxos = [
            UTXO(txid="tx1", vout=0, amount=1000, script_pubkey="", confirmations=0)
        ]

        result = selector.select(utxos, 500, fee_per_byte=1)

        assert result.success is False

    def test_max_inputs_limit(self):
        selector = CoinSelector(max_inputs=2)
        utxos = [
            UTXO(txid=f"tx{i}", vout=0, amount=100000, script_pubkey="", confirmations=6)
            for i in range(5)
        ]

        result = selector.select(utxos, 80000, fee_per_byte=1)

        assert result.success is True
        assert len(result.utxos) <= 2


class TestCoinSelectionResult:
    """Tests for CoinSelectionResult."""

    def test_effective_amount(self):
        result = CoinSelectionResult(
            utxos=[],
            total_amount=200000,
            fee=5000,
            excess=0,
            success=True,
        )
        assert result.effective_amount == 195000

    def test_can_send(self):
        result = CoinSelectionResult(
            utxos=[],
            total_amount=210000,
            fee=5000,
            excess=5000,
            success=True,
        )
        assert result.can_send == 200000


class TestWallet:
    """Tests for Wallet."""

    def test_create_wallet(self):
        wallet = Wallet(wallet_id="test1", name="Test Wallet")
        assert wallet.wallet_id == "test1"
        assert wallet.name == "Test Wallet"

    def test_balance(self):
        wallet = Wallet(wallet_id="test1")
        wallet.utxos = [
            UTXO(txid="tx1", vout=0, amount=100000, script_pubkey="", confirmations=6),
            UTXO(txid="tx2", vout=0, amount=50000, script_pubkey="", confirmations=6),
        ]
        assert wallet.balance == 150000

    def test_confirmed_balance(self):
        wallet = Wallet(wallet_id="test1")
        wallet.utxos = [
            UTXO(txid="tx1", vout=0, amount=100000, script_pubkey="", confirmations=6),
            UTXO(txid="tx2", vout=0, amount=50000, script_pubkey="", confirmations=3),
        ]
        assert wallet.confirmed_balance == 100000

    def test_get_stats(self):
        wallet = Wallet(wallet_id="test1", name="Test")
        wallet.utxos = [
            UTXO(txid="tx1", vout=0, amount=100000, script_pubkey="", confirmations=6),
            UTXO(txid="tx2", vout=0, amount=50000, script_pubkey="", confirmations=6),
        ]
        stats = wallet.get_stats()
        assert stats.total_utxos == 2
        assert stats.total_balance == 150000
        assert stats.largest_utxo == 100000

    def test_serialize_to_dict(self):
        wallet = Wallet(wallet_id="test1", name="Test")
        wallet.utxos = [
            UTXO(txid="tx1", vout=0, amount=100000, script_pubkey="", confirmations=6),
        ]

        d = wallet.to_dict()
        assert d["wallet_id"] == "test1"
        assert len(d["utxos"]) == 1

    def test_file_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "wallet.json"

            wallet = Wallet(wallet_id="test1", name="Test")
            wallet.utxos = [
                UTXO(txid="tx1", vout=0, amount=100000, script_pubkey="", confirmations=6),
            ]
            wallet.to_file(path)

            loaded = Wallet.from_file(path)
            assert loaded.wallet_id == "test1"
            assert len(loaded.utxos) == 1
            assert loaded.utxos[0].amount == 100000


class TestWalletManager:
    """Tests for WalletManager."""

    def test_create_wallet(self):
        rpc = MagicMock()
        manager = WalletManager(rpc)

        wallet = manager.create_wallet("Test Wallet", "wallet1")
        assert wallet.wallet_id == "wallet1"
        assert "wallet1" in manager.list_wallets()

    def test_get_wallet(self):
        rpc = MagicMock()
        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1")

        wallet = manager.get_wallet("w1")
        assert wallet is not None
        assert wallet.wallet_id == "w1"

    def test_delete_wallet(self):
        rpc = MagicMock()
        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1")

        assert manager.delete_wallet("w1") is True
        assert manager.get_wallet("w1") is None

    def test_add_address(self):
        rpc = MagicMock()
        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1")

        assert manager.add_address("w1", "XvX26g...") is True
        wallet = manager.get_wallet("w1")
        assert "XvX26g..." in wallet.addresses

    def test_sync_wallet(self):
        rpc = MagicMock()
        rpc.listunspent.return_value = [
            {"txid": "tx1", "vout": 0, "amount": "0.001", "scriptPubKey": "", "confirmations": 6}
        ]

        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1", addresses=["addr1"])

        stats = manager.sync_wallet("w1")

        assert stats.total_utxos == 1
        assert stats.total_balance == 100000

    def test_sync_all(self):
        rpc = MagicMock()
        rpc.listunspent.return_value = [
            {"txid": "tx1", "vout": 0, "amount": "0.001", "scriptPubKey": "", "confirmations": 6}
        ]

        manager = WalletManager(rpc)
        manager.create_wallet("Test1", "w1")
        manager.create_wallet("Test2", "w2")

        stats = manager.sync_all()
        assert len(stats) == 2

    def test_select_coins(self):
        rpc = MagicMock()
        rpc.listunspent.return_value = [
            {"txid": "tx1", "vout": 0, "amount": "0.001", "scriptPubKey": "", "confirmations": 6}
        ]

        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1")

        result = manager.select_coins("w1", 50000, fee_per_byte=1)

        assert result.success is True

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir)
            rpc = MagicMock()
            manager = WalletManager(rpc, storage_path=storage)

            manager.create_wallet("Test1", "w1")
            manager.create_wallet("Test2", "w2")

            manager2 = WalletManager(rpc, storage_path=storage)
            assert len(manager2.list_wallets()) == 2

    def test_full_stats_report(self):
        rpc = MagicMock()
        rpc.listunspent.return_value = []

        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1")

        report = manager.full_stats_report()
        assert "WALLET MANAGER REPORT" in report
        assert "w1" in report


class TestConcurrency:
    """Tests for thread safety."""

    def test_concurrent_wallet_access(self):
        rpc = MagicMock()
        rpc.listunspent.return_value = []

        manager = WalletManager(rpc)
        manager.create_wallet("Test", "w1")

        results = []

        def worker():
            for _ in range(10):
                manager.get_wallet("w1")
                stats = manager.get_stats("w1")
                results.append(stats)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 50