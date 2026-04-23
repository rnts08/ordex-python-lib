"""
Mempool Service for monitoring unconfirmed transactions and fee estimation.

Features:
- Mempool contents monitoring
- Fee estimation (economic/half-hour/hour targets)
- Unconfirmed UTXO tracking
- Transaction tracking and callbacks
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FeeEstimateMode(Enum):
    """Fee estimation mode."""
    ECONOMIC = "economic"
    HALF_HOUR = "half_hour"
    HOUR = "hour"


@dataclass
class FeeEstimate:
    """Fee rate estimate."""
    mode: FeeEstimateMode
    feerate: float
    blocks: int
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "feerate": self.feerate,
            "blocks": self.blocks,
            "timestamp": self.timestamp,
        }


@dataclass
class MempoolStats:
    """Mempool statistics."""
    size_bytes: int = 0
    usage_bytes: int = 0
    transaction_count: int = 0
    fee_percentiles: List[float] = field(default_factory=list)
    min_fee: float = 0.0
    max_fee: float = 0.0
    avg_fee: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size_bytes": self.size_bytes,
            "usage_bytes": self.usage_bytes,
            "transaction_count": self.transaction_count,
            "fee_percentiles": self.fee_percentiles,
            "min_fee": self.min_fee,
            "max_fee": self.max_fee,
            "avg_fee": self.avg_fee,
            "timestamp": self.timestamp,
        }


@dataclass
class TrackedTransaction:
    """A transaction being tracked."""
    txid: str
    added_at: str = ""
    size_bytes: int = 0
    fee: float = 0.0
    fee_rate: float = 0.0
    status: str = "pending"
    confirmations: int = 0
    block_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txid": self.txid,
            "added_at": self.added_at,
            "size_bytes": self.size_bytes,
            "fee": self.fee,
            "fee_rate": self.fee_rate,
            "status": self.status,
            "confirmations": self.confirmations,
            "block_hash": self.block_hash,
            "metadata": self.metadata,
        }


class MempoolService:
    """Mempool monitoring and fee estimation service.

    Features:
    - Get mempool contents
    - Fee estimation
    - Unconfirmed UTXO tracking
    - Transaction tracking with callbacks
    """

    def __init__(self, rpc_client: Optional[Any] = None) -> None:
        self._rpc_client = rpc_client
        self._tracked_txs: Dict[str, TrackedTransaction] = {}
        self._lock = threading.Lock()
        self._callbacks_new_tx: List[Callable[[str], None]] = []
        self._callbacks_confirmed: List[Callable[[str, str], None]] = []
        self._callbacks_removed: List[Callable[[str], None]] = []
        self._mempool_cache: Optional[Dict[str, Any]] = None
        self._mempool_cache_time: float = 0
        self._cache_ttl: float = 5.0

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client for blockchain queries."""
        self._rpc_client = rpc_client

    def get_mempool(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Get mempool contents.

        Args:
            refresh: Force refresh from node (bypass cache)

        Returns:
            List of mempool transaction info
        """
        if not refresh and self._mempool_cache and (time.time() - self._mempool_cache_time) < self._cache_ttl:
            return self._mempool_cache.get("txs", [])

        if self._rpc_client is None:
            return []

        try:
            result = self._rpc_client.getrawmempool(verbose=True)
            txs = []
            for txid, info in result.items():
                txs.append({
                    "txid": txid,
                    "size": info.get("size", 0),
                    "fee": info.get("fee", 0),
                    "feerate": info.get("feerate", 0),
                    "time": info.get("time", 0),
                    "height": info.get("height", 0),
                    "depends": info.get("depends", []),
                    "spent": info.get("spent", []),
                })
            self._mempool_cache = {"txs": txs, "timestamp": datetime.now(timezone.utc).isoformat()}
            self._mempool_cache_time = time.time()
            return txs
        except Exception as e:
            logger.error("Failed to get mempool: %s", e)
            return []

    def get_stats(self) -> MempoolStats:
        """Get mempool statistics."""
        mempool = self.get_mempool(refresh=True)

        if not mempool:
            return MempoolStats(timestamp=datetime.now(timezone.utc).isoformat())

        sizes = [tx.get("size", 0) for tx in mempool]
        feerates = [tx.get("feerate", 0) for tx in mempool]

        fee_percentiles = []
        if feerates:
            sorted_fees = sorted(feerates)
            for p in [10, 25, 50, 75, 90]:
                idx = int(len(sorted_fees) * p / 100)
                fee_percentiles.append(sorted_fees[idx])

        return MempoolStats(
            size_bytes=sum(sizes),
            transaction_count=len(mempool),
            fee_percentiles=fee_percentiles,
            min_fee=min(feerates) if feerates else 0,
            max_fee=max(feerates) if feerates else 0,
            avg_fee=sum(feerates) / len(feerates) if feerates else 0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_fees(self, mode: FeeEstimateMode = FeeEstimateMode.ECONOMIC) -> FeeEstimate:
        """Get fee estimate.

        Args:
            mode: Fee estimation mode

        Returns:
            FeeEstimate with feerate
        """
        if self._rpc_client is None:
            blocks = self._get_blocks_for_mode(mode)
            return FeeEstimate(
                mode=mode,
                feerate=self._get_default_feerate(mode),
                blocks=blocks,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            conf_target = self._get_blocks_for_mode(mode)
            estimate = self._rpc_client.estimatesmartfee(conf_target)
            feerate = estimate.get("feerate", self._get_default_feerate(mode))
            return FeeEstimate(
                mode=mode,
                feerate=feerate,
                blocks=conf_target,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.error("Failed to get fee estimate: %s", e)
            return FeeEstimate(
                mode=mode,
                feerate=self._get_default_feerate(mode),
                blocks=self._get_blocks_for_mode(mode),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

    def _get_blocks_for_mode(self, mode: FeeEstimateMode) -> int:
        """Map mode to block target."""
        mapping = {
            FeeEstimateMode.ECONOMIC: 6,
            FeeEstimateMode.HALF_HOUR: 3,
            FeeEstimateMode.HOUR: 1,
        }
        return mapping.get(mode, 6)

    def _get_default_feerate(self, mode: FeeEstimateMode) -> float:
        """Get default feerate for mode when RPC unavailable."""
        mapping = {
            FeeEstimateMode.ECONOMIC: 10.0,
            FeeEstimateMode.HALF_HOUR: 20.0,
            FeeEstimateMode.HOUR: 50.0,
        }
        return mapping.get(mode, 10.0)

    def get_utxos(self) -> List[Dict[str, Any]]:
        """Get all UTXOs in the mempool (unconfirmed outputs)."""
        mempool = self.get_mempool()
        utxos = []

        for tx in mempool:
            txid = tx.get("txid", "")
            size = tx.get("size", 0)
            fee = tx.get("fee", 0)
            if fee > 0 and size > 0:
                feerate = (fee * 100000000) / size
            else:
                feerate = 0
            utxos.append({
                "txid": txid,
                "vout": 0,
                "amount": fee,
                "size": size,
                "feerate": feerate,
            })

        return utxos

    def get_transaction(self, txid: str) -> Optional[Dict[str, Any]]:
        """Get info about a tracked transaction.

        Args:
            txid: Transaction ID

        Returns:
            Transaction info if tracked, None otherwise
        """
        with self._lock:
            if txid in self._tracked_txs:
                return self._tracked_txs[txid].to_dict()

        mempool = self.get_mempool()
        for tx in mempool:
            if tx.get("txid") == txid:
                return tx

        return None

    def track_transaction(
        self,
        txid: str,
        size_bytes: int = 0,
        fee: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a transaction for updates.

        Args:
            txid: Transaction ID to track
            size_bytes: Transaction size
            fee: Transaction fee
            metadata: Additional metadata
        """
        with self._lock:
            fee_rate = (fee * 100000000) / size_bytes if size_bytes > 0 else 0
            self._tracked_txs[txid] = TrackedTransaction(
                txid=txid,
                added_at=datetime.now(timezone.utc).isoformat(),
                size_bytes=size_bytes,
                fee=fee,
                fee_rate=fee_rate,
                status="pending",
                metadata=metadata or {},
            )
            logger.info("Tracking transaction: %s", txid)

    def untrack_transaction(self, txid: str) -> bool:
        """Stop tracking a transaction.

        Args:
            txid: Transaction ID

        Returns:
            True if transaction was being tracked
        """
        with self._lock:
            if txid in self._tracked_txs:
                del self._tracked_txs[txid]
                logger.info("Untracked transaction: %s", txid)
                return True
            return False

    def update_tracked_transactions(self, confirmed_ids: Set[str], block_hash: Optional[str] = None) -> None:
        """Update status of tracked transactions.

        Args:
            confirmed_ids: Set of transaction IDs that are now confirmed
            block_hash: Hash of block containing confirmations
        """
        with self._lock:
            for txid in self._tracked_txs:
                tracked = self._tracked_txs[txid]
                if txid in confirmed_ids:
                    old_status = tracked.status
                    tracked.status = "confirmed"
                    tracked.confirmations += 1
                    tracked.block_hash = block_hash
                    if old_status == "pending":
                        for callback in self._callbacks_confirmed:
                            try:
                                callback(txid, block_hash or "")
                            except Exception as e:
                                logger.error("Confirmed callback error: %s", e)
                elif tracked.status == "pending":
                    mempool = self.get_mempool()
                    if not any(tx.get("txid") == txid for tx in mempool):
                        old_status = tracked.status
                        tracked.status = "removed"
                        if old_status == "pending":
                            for callback in self._callbacks_removed:
                                try:
                                    callback(txid)
                                except Exception as e:
                                    logger.error("Removed callback error: %s", e)

    def mark_confirmed(self, txid: str, block_hash: str) -> None:
        """Mark a transaction as confirmed.

        Args:
            txid: Transaction ID
            block_hash: Hash of confirming block
        """
        with self._lock:
            if txid in self._tracked_txs:
                tracked = self._tracked_txs[txid]
                tracked.status = "confirmed"
                tracked.confirmations += 1
                tracked.block_hash = block_hash
                for callback in self._callbacks_confirmed:
                    try:
                        callback(txid, block_hash)
                    except Exception as e:
                        logger.error("Confirmed callback error: %s", e)

    def on_new_transaction(self, callback: Callable[[str], None]) -> None:
        """Register callback for new transactions in mempool.

        Args:
            callback: Function called with txid
        """
        self._callbacks_new_tx.append(callback)

    def on_transaction_confirmed(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for transaction confirmations.

        Args:
            callback: Function(txid, block_hash)
        """
        self._callbacks_confirmed.append(callback)

    def on_transaction_removed(self, callback: Callable[[str], None]) -> None:
        """Register callback for removed transactions.

        Args:
            callback: Function called with txid
        """
        self._callbacks_removed.append(callback)

    def get_tracked_count(self) -> int:
        """Get count of tracked transactions."""
        with self._lock:
            return len(self._tracked_txs)

    def get_pending_transactions(self) -> List[Dict[str, Any]]:
        """Get all pending (unconfirmed) tracked transactions."""
        with self._lock:
            return [
                tx.to_dict() for tx in self._tracked_txs.values()
                if tx.status == "pending"
            ]

    def clear_cache(self) -> None:
        """Clear the mempool cache."""
        self._mempool_cache = None
        self._mempool_cache_time = 0

    def check_mempool_diff(self) -> Dict[str, List[str]]:
        """Check for new and removed transactions since last call.

        Returns:
            Dict with 'added' and 'removed' txids
        """
        current_mempool = self.get_mempool(refresh=True)
        current_ids = {tx.get("txid") for tx in current_mempool}

        with self._lock:
            tracked_ids = {txid for txid in self._tracked_txs}

        added = list(current_ids - tracked_ids)
        removed = list(tracked_ids - current_ids)

        for txid in added:
            for callback in self._callbacks_new_tx:
                try:
                    callback(txid)
                except Exception as e:
                    logger.error("New tx callback error: %s", e)

        if removed:
            for txid in removed:
                if txid in self._tracked_txs:
                    tracked = self._tracked_txs[txid]
                    if tracked.status == "pending":
                        tracked.status = "removed"
                        for callback in self._callbacks_removed:
                            try:
                                callback(txid)
                            except Exception as e:
                                logger.error("Removed callback error: %s", e)

        return {"added": added, "removed": removed}