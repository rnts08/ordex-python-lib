"""
Transaction Tracker Service for tracking pending transactions and confirmations.

Features:
- Track outgoing transactions
- Confirmation tracking (0-conf, 1-conf, 6-conf)
- Balance delta tracking
- Replace-by-fee tracking
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConfirmationLevel(Enum):
    """Confirmation level thresholds."""
    ZERO_CONF = 0
    ONE_CONF = 1
    SIX_CONF = 6


@dataclass
class TxTrackingInfo:
    """Transaction tracking information."""
    txid: str
    wallet_id: str
    amount: int
    address: str = ""
    fee: int = 0
    fee_rate: float = 0.0
    status: str = "pending"
    confirmations: int = 0
    added_at: str = ""
    first_seen: Optional[str] = None
    confirmed_at: Optional[str] = None
    replaced_by: Optional[str] = None
    replaces: Optional[str] = None
    block_hash: Optional[str] = None
    block_height: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txid": self.txid,
            "wallet_id": self.wallet_id,
            "amount": self.amount,
            "address": self.address,
            "fee": self.fee,
            "fee_rate": self.fee_rate,
            "status": self.status,
            "confirmations": self.confirmations,
            "added_at": self.added_at,
            "first_seen": self.first_seen,
            "confirmed_at": self.confirmed_at,
            "replaced_by": self.replaced_by,
            "replaces": self.replaces,
            "block_hash": self.block_hash,
            "block_height": self.block_height,
            "metadata": self.metadata,
        }


@dataclass
class BalanceDelta:
    """Balance change information."""
    wallet_id: str
    txid: str
    old_balance: int = 0
    new_balance: int = 0
    delta: int = 0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_id": self.wallet_id,
            "txid": self.txid,
            "old_balance": self.old_balance,
            "new_balance": self.new_balance,
            "delta": self.delta,
            "timestamp": self.timestamp,
        }


@dataclass
class TxHistoryEntry:
    """Transaction history entry."""
    txid: str
    wallet_id: str
    amount: int
    fee: int
    confirmations: int
    timestamp: str
    block_height: Optional[int] = None
    is_replaced: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txid": self.txid,
            "wallet_id": self.wallet_id,
            "amount": self.amount,
            "fee": self.fee,
            "confirmations": self.confirmations,
            "timestamp": self.timestamp,
            "block_height": self.block_height,
            "is_replaced": self.is_replaced,
        }


class TxTracker:
    """Track transactions for confirmation status.

    Features:
    - Track outgoing transactions
    - Monitor confirmation levels
    - RBF tracking
    - Balance delta tracking
    """

    def __init__(
        self,
        rpc_client: Optional[Any] = None,
        block_service: Optional[Any] = None,
    ) -> None:
        self._rpc_client = rpc_client
        self._block_service = block_service
        self._lock = threading.Lock()
        self._tracked_txs: Dict[str, TxTrackingInfo] = {}
        self._wallet_txs: Dict[str, List[str]] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "zero_conf": [],
            "one_conf": [],
            "six_conf": [],
            "confirmed": [],
            "replaced": [],
            "failed": [],
        }
        self._balance_callbacks: Dict[str, Callable] = {}
        self._current_block_height = 0

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client."""
        self._rpc_client = rpc_client

    def set_block_service(self, block_service: Any) -> None:
        """Set the block service."""
        self._block_service = block_service

    def track(
        self,
        txid: str,
        wallet_id: str,
        amount: int,
        fee: int = 0,
        address: str = "",
        fee_rate: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a transaction.

        Args:
            txid: Transaction ID
            wallet_id: Wallet identifier
            amount: Transaction amount (positive for receive, negative for send)
            fee: Transaction fee
            address: Destination address
            fee_rate: Fee rate in sat/vB
            metadata: Additional metadata
        """
        with self._lock:
            self._tracked_txs[txid] = TxTrackingInfo(
                txid=txid,
                wallet_id=wallet_id,
                amount=amount,
                fee=fee,
                fee_rate=fee_rate,
                address=address,
                status="pending",
                confirmations=0,
                added_at=datetime.now(timezone.utc).isoformat(),
                first_seen=datetime.now(timezone.utc).isoformat(),
                metadata=metadata or {},
            )

            if wallet_id not in self._wallet_txs:
                self._wallet_txs[wallet_id] = []
            self._wallet_txs[wallet_id].append(txid)

            logger.info("Tracking transaction %s for wallet %s", txid, wallet_id)

    def untrack(self, txid: str) -> bool:
        """Stop tracking a transaction.

        Args:
            txid: Transaction ID

        Returns:
            True if transaction was being tracked
        """
        with self._lock:
            if txid in self._tracked_txs:
                info = self._tracked_txs[txid]
                wallet_id = info.wallet_id
                if wallet_id in self._wallet_txs:
                    if txid in self._wallet_txs[wallet_id]:
                        self._wallet_txs[wallet_id].remove(txid)
                del self._tracked_txs[txid]
                return True
            return False

    def get_status(self, txid: str) -> Optional[TxTrackingInfo]:
        """Get tracking status for a transaction.

        Args:
            txid: Transaction ID

        Returns:
            TxTrackingInfo or None
        """
        with self._lock:
            return self._tracked_txs.get(txid)

    def get_confirmations(self, txid: str) -> int:
        """Get confirmation count for a transaction.

        Args:
            txid: Transaction ID

        Returns:
            Number of confirmations
        """
        info = self.get_status(txid)
        if info is None:
            return 0
        return info.confirmations

    def update_confirmations(
        self,
        txid: str,
        confirmations: int,
        block_hash: Optional[str] = None,
        block_height: Optional[int] = None,
    ) -> None:
        """Update confirmation count for a transaction.

        Args:
            txid: Transaction ID
            confirmations: New confirmation count
            block_hash: Hash of confirming block
            block_height: Height of confirming block
        """
        with self._lock:
            if txid not in self._tracked_txs:
                return

            info = self._tracked_txs[txid]
            old_confirmations = info.confirmations
            info.confirmations = confirmations

            if block_hash:
                info.block_hash = block_hash
            if block_height:
                info.block_height = block_height

            if confirmations >= 6 and info.status != "confirmed":
                info.status = "confirmed"
                info.confirmed_at = datetime.now(timezone.utc).isoformat()
                self._emit_callback("confirmed", txid, info)
            elif confirmations >= 1 and old_confirmations < 1:
                info.status = "confirmed"
                self._emit_callback("one_conf", txid, info)

            if old_confirmations == 0 and confirmations > 0:
                self._emit_callback("zero_conf", txid, info)

    def mark_confirmed(
        self,
        txid: str,
        block_hash: str,
        block_height: int,
    ) -> None:
        """Mark a transaction as confirmed.

        Args:
            txid: Transaction ID
            block_hash: Hash of confirming block
            block_height: Height of block
        """
        with self._lock:
            if txid not in self._tracked_txs:
                return

            info = self._tracked_txs[txid]
            info.status = "confirmed"
            info.confirmations = max(info.confirmations, 1)
            info.block_hash = block_hash
            info.block_height = block_height
            info.confirmed_at = datetime.now(timezone.utc).isoformat()

            self._emit_callback("confirmed", txid, info)

    def mark_replaced(
        self,
        original_txid: str,
        replacement_txid: str,
    ) -> None:
        """Mark a transaction as replaced by RBF.

        Args:
            original_txid: Original transaction ID
            replacement_txid: Replacement transaction ID
        """
        with self._lock:
            if original_txid not in self._tracked_txs:
                return

            original = self._tracked_txs[original_txid]
            original.status = "replaced"
            original.replaced_by = replacement_txid

            if replacement_txid in self._tracked_txs:
                replacement = self._tracked_txs[replacement_txid]
                replacement.replaces = original_txid

            self._emit_callback("replaced", original_txid, original)

    def on_zero_conf(self, callback: Callable[[str, TxTrackingInfo], None]) -> None:
        """Register callback for 0-confirmations (first seen in block).

        Args:
            callback: Function(txid, TxTrackingInfo)
        """
        self._callbacks["zero_conf"].append(callback)

    def on_one_conf(self, callback: Callable[[str, TxTrackingInfo], None]) -> None:
        """Register callback for first confirmation.

        Args:
            callback: Function(txid, TxTrackingInfo)
        """
        self._callbacks["one_conf"].append(callback)

    def on_six_conf(self, callback: Callable[[str, TxTrackingInfo], None]) -> None:
        """Register callback for 6 confirmations.

        Args:
            callback: Function(txid, TxTrackingInfo)
        """
        self._callbacks["six_conf"].append(callback)

    def on_confirmation(
        self,
        callback: Callable[[str, TxTrackingInfo], None],
    ) -> None:
        """Register callback for confirmations.

        Args:
            callback: Function(txid, TxTrackingInfo)
        """
        self._callbacks["confirmed"].append(callback)

    def on_replaced(
        self,
        callback: Callable[[str, TxTrackingInfo], None],
    ) -> None:
        """Register callback for replaced transactions.

        Args:
            callback: Function(txid, TxTrackingInfo)
        """
        self._callbacks["replaced"].append(callback)

    def _emit_callback(
        self,
        event: str,
        txid: str,
        info: TxTrackingInfo,
    ) -> None:
        """Emit callbacks for an event.

        Args:
            event: Event name
            txid: Transaction ID
            info: Tracking info
        """
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(txid, info)
                except Exception as e:
                    logger.error("Callback error for %s: %s", event, e)

    def get_pending(self, wallet_id: str) -> List[TxTrackingInfo]:
        """Get pending transactions for a wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            List of pending transactions
        """
        with self._lock:
            pending = []
            if wallet_id in self._wallet_txs:
                for txid in self._wallet_txs[wallet_id]:
                    if txid in self._tracked_txs:
                        info = self._tracked_txs[txid]
                        if info.status == "pending":
                            pending.append(info)
            return pending

    def get_confirmed(self, wallet_id: str) -> List[TxTrackingInfo]:
        """Get confirmed transactions for a wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            List of confirmed transactions
        """
        with self._lock:
            confirmed = []
            if wallet_id in self._wallet_txs:
                for txid in self._wallet_txs[wallet_id]:
                    if txid in self._tracked_txs:
                        info = self._tracked_txs[txid]
                        if info.status == "confirmed":
                            confirmed.append(info)
            return confirmed

    def get_tracked_count(self) -> int:
        """Get count of tracked transactions."""
        with self._lock:
            return len(self._tracked_txs)

    def scan_mempool(self) -> Dict[str, int]:
        """Scan mempool for tracked transactions.

        Returns:
            Dict with 'found' and 'not_found' counts
        """
        if self._rpc_client is None:
            return {"found": 0, "not_found": 0}

        try:
            mempool = self._rpc_client.getrawmempool(verbose=False)
            found = 0
            not_found = 0

            with self._lock:
                for txid in list(self._tracked_txs.keys()):
                    if self._tracked_txs[txid].status == "pending":
                        if txid in mempool:
                            found += 1
                        else:
                            not_found += 1

            return {"found": found, "not_found": not_found}
        except Exception as e:
            logger.error("Failed to scan mempool: %s", e)
            return {"found": 0, "not_found": 0}


class WalletTracker:
    """Track wallet balance changes and transaction history.

    Features:
    - Balance history
    - UTXO changes
    - Transaction history
    - Balance change callbacks
    """

    def __init__(self, rpc_client: Optional[Any] = None) -> None:
        self._rpc_client = rpc_client
        self._lock = threading.Lock()
        self._balance_history: Dict[str, List[BalanceDelta]] = {}
        self._current_balances: Dict[str, int] = {}
        self._callbacks: Dict[str, Callable] = {}

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client."""
        self._rpc_client = rpc_client

    def track_balance(self, wallet_id: str, balance: int) -> None:
        """Track balance for a wallet.

        Args:
            wallet_id: Wallet identifier
            balance: Current balance in satoshis
        """
        with self._lock:
            old_balance = self._current_balances.get(wallet_id, 0)
            if old_balance != balance:
                delta = balance - old_balance
                entry = BalanceDelta(
                    wallet_id=wallet_id,
                    txid="",
                    old_balance=old_balance,
                    new_balance=balance,
                    delta=delta,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

                if wallet_id not in self._balance_history:
                    self._balance_history[wallet_id] = []
                self._balance_history[wallet_id].append(entry)

                self._current_balances[wallet_id] = balance

                if wallet_id in self._callbacks:
                    try:
                        self._callbacks[wallet_id](entry)
                    except Exception as e:
                        logger.error("Balance callback error: %s", e)

    def get_balance(self, wallet_id: str) -> int:
        """Get current balance for a wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Balance in satoshis
        """
        with self._lock:
            return self._current_balances.get(wallet_id, 0)

    def get_history(
        self,
        wallet_id: str,
        limit: int = 100,
    ) -> List[BalanceDelta]:
        """Get balance history for a wallet.

        Args:
            wallet_id: Wallet identifier
            limit: Maximum entries to return

        Returns:
            List of balance changes
        """
        with self._lock:
            history = self._balance_history.get(wallet_id, [])
            return history[-limit:]

    def on_balance_change(
        self,
        wallet_id: str,
        callback: Callable[[BalanceDelta], None],
    ) -> None:
        """Register callback for balance changes.

        Args:
            wallet_id: Wallet identifier
            callback: Function(BalanceDelta)
        """
        with self._lock:
            self._callbacks[wallet_id] = callback