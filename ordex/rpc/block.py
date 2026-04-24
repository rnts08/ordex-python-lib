"""
Block Service for block data, headers, and notifications.

Features:
- Block retrieval and caching
- Header verification
- New block subscriptions
- Reorg detection and handling
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BlockCacheType(Enum):
    """Block cache type."""
    HEADER = "header"
    FULL = "full"


@dataclass
class BlockHeader:
    """Block header data."""
    hash: str
    height: int
    version: int = 0
    prev_blockhash: str = ""
    merkle_root: str = ""
    timestamp: int = 0
    bits: int = 0
    nonce: int = 0
    size: int = 0
    weight: int = 0
    timestamp_str: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "height": self.height,
            "version": self.version,
            "prev_blockhash": self.prev_blockhash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "bits": self.bits,
            "nonce": self.nonce,
            "size": self.size,
            "weight": self.weight,
            "timestamp_str": self.timestamp_str,
        }


@dataclass
class BlockInfo:
    """Full block information."""
    hash: str
    height: int
    version: int = 0
    size: int = 0
    weight: int = 0
    merkleroot: str = ""
    tx: List[str] = field(default_factory=list)
    time: int = 0
    mediantime: int = 0
    nonce: int = 0
    bits: str = ""
    difficulty: float = 0.0
    chainwork: str = ""
    previousblockhash: str = ""
    nextblockhash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hash": self.hash,
            "height": self.height,
            "version": self.version,
            "size": self.size,
            "weight": self.weight,
            "merkleroot": self.merkleroot,
            "tx": self.tx,
            "time": self.time,
            "mediantime": self.mediantime,
            "nonce": self.nonce,
            "bits": self.bits,
            "difficulty": self.difficulty,
            "chainwork": self.chainwork,
            "previousblockhash": self.previousblockhash,
            "nextblockhash": self.nextblockhash,
        }


@dataclass
class ReorgEvent:
    """Reorganization event data."""
    old_height: int
    new_height: int
    old_hash: str
    new_hash: str
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "old_height": self.old_height,
            "new_height": self.new_height,
            "old_hash": self.old_hash,
            "new_hash": self.new_hash,
            "timestamp": self.timestamp,
        }


class LRUCache:
    """Thread-safe LRU cache for block data."""

    def __init__(self, max_size: int = 1000):
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
            self._cache[key] = value

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


class BlockService:
    """Block data service with caching and notifications.

    Features:
    - Block/header retrieval
    - LRU caching for performance
    - New block subscriptions
    - Reorg detection and handling
    """

    def __init__(
        self,
        rpc_client: Optional[Any] = None,
        cache_size: int = 1000,
    ) -> None:
        self._rpc_client = rpc_client
        self._header_cache = LRUCache(cache_size)
        self._block_cache = LRUCache(cache_size)
        self._lock = threading.Lock()
        self._current_tip: Optional[BlockHeader] = None
        self._callbacks_new_block: List[Callable[[BlockHeader], None]] = []
        self._callbacks_reorg: List[Callable[[ReorgEvent], None]] = []
        self._callbacks_confirmation: List[Callable[[str, int], None]] = []
        self._subscription_id = 0
        self._subscriptions: Dict[int, Callable] = {}
        self._last_reorg_height = 0

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client for blockchain queries."""
        self._rpc_client = rpc_client

    def get_block(self, block_hash: str, verbosity: int = 1) -> Optional[Dict[str, Any]]:
        """Get block data.

        Args:
            block_hash: Block hash
            verbosity: 0=raw hex, 1=JSON object, 2=JSON with tx details

        Returns:
            Block data or None if not found
        """
        if verbosity == 0:
            cached = self._block_cache.get(block_hash)
            if cached:
                return cached

        if self._rpc_client is None:
            return None

        try:
            if verbosity == 0:
                result = self._rpc_client.getblock(block_hash, verbosity=0)
                block_info = {"data": result}
                self._block_cache.set(block_hash, block_info)
                return block_info
            else:
                result = self._rpc_client.getblock(block_hash, verbosity=verbosity)
                return result
        except Exception as e:
            logger.error("Failed to get block %s: %s", block_hash, e)
            return None

    def get_header(self, height: int) -> Optional[BlockHeader]:
        """Get block header at height.

        Args:
            height: Block height

        Returns:
            BlockHeader or None
        """
        cache_key = f"height:{height}"
        cached = self._header_cache.get(cache_key)
        if cached:
            return cached

        if self._rpc_client is None:
            return None

        try:
            block_hash = self._rpc_client.getblockhash(height)
            if not block_hash:
                return None
            return self.get_header_by_hash(block_hash)
        except Exception as e:
            logger.error("Failed to get header at height %d: %s", height, e)
            return None

    def get_header_by_hash(self, block_hash: str) -> Optional[BlockHeader]:
        """Get block header by hash.

        Args:
            block_hash: Block hash

        Returns:
            BlockHeader or None
        """
        cache_key = f"hash:{block_hash}"
        cached = self._header_cache.get(cache_key)
        if cached:
            return cached

        if self._rpc_client is None:
            return None

        try:
            header_data = self._rpc_client.getblockheader(block_hash, verbose=True)
            header = BlockHeader(
                hash=header_data.get("hash", block_hash),
                height=header_data.get("height", 0),
                version=header_data.get("version", 0),
                prev_blockhash=header_data.get("previousblockhash", ""),
                merkle_root=header_data.get("merkleroot", ""),
                timestamp=header_data.get("time", 0),
                bits=header_data.get("bits", 0),
                nonce=header_data.get("nonce", 0),
                size=header_data.get("size", 0),
                weight=header_data.get("weight", 0),
                timestamp_str=datetime.fromtimestamp(
                    header_data.get("time", 0), tz=timezone.utc
                ).isoformat() if header_data.get("time") else "",
            )
            self._header_cache.set(cache_key, header)
            self._header_cache.set(f"height:{header.height}", header)
            return header
        except Exception as e:
            logger.error("Failed to get header %s: %s", block_hash, e)
            return None

    def verify_header(self, header: BlockHeader) -> bool:
        """Verify a block header (basic checks).

        Args:
            header: BlockHeader to verify

        Returns:
            True if header appears valid
        """
        if not header.hash:
            return False
        if header.height < 0:
            return False
        if not header.prev_blockhash and header.height > 0:
            return False
        if header.size <= 0:
            return False
        if header.bits == 0:
            return False
        return True

    def verify_chain(self, start_height: int, count: int = 6) -> bool:
        """Verify chain of headers.

        Args:
            start_height: Starting height
            count: Number of headers to verify

        Returns:
            True if chain is valid
        """
        for i in range(count):
            height = start_height + i
            header = self.get_header(height)
            if header is None:
                return False
            if not self.verify_header(header):
                return False
            if i > 0:
                prev_header = self.get_header(height - 1)
                if prev_header and header.prev_blockhash != prev_header.hash:
                    return False
        return True

    def get_tip(self) -> Optional[Dict[str, Any]]:
        """Get current chain tip.

        Returns:
            Tip info with hash and height
        """
        if self._current_tip:
            return self._current_tip.to_dict()

        if self._rpc_client is None:
            return None

        try:
            block_hash = self._rpc_client.getbestblockhash()
            if block_hash:
                header = self.get_header_by_hash(block_hash)
                if header:
                    with self._lock:
                        self._current_tip = header
                    return header.to_dict()
        except Exception as e:
            logger.error("Failed to get tip: %s", e)

        return None

    def update_tip(self) -> Optional[BlockHeader]:
        """Update current tip from node.

        Returns:
            Updated tip header
        """
        if self._rpc_client is None:
            return self._current_tip

        try:
            block_hash = self._rpc_client.getbestblockhash()
            if not block_hash:
                return self._current_tip

            old_tip = self._current_tip
            new_header = self.get_header_by_hash(block_hash)

            if new_header:
                with self._lock:
                    self._current_tip = new_header

                if old_tip and new_header.height > old_tip.height:
                    for callback in self._callbacks_new_block:
                        try:
                            callback(new_header)
                        except Exception as e:
                            logger.error("New block callback error: %s", e)

                if old_tip and new_header.hash != old_tip.hash:
                    reorg = ReorgEvent(
                        old_height=old_tip.height,
                        new_height=new_header.height,
                        old_hash=old_tip.hash,
                        new_hash=new_header.hash,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                    )
                    with self._lock:
                        self._last_reorg_height = new_header.height
                    for callback in self._callbacks_reorg:
                        try:
                            callback(reorg)
                        except Exception as e:
                            logger.error("Reorg callback error: %s", e)

                self._invalidate_cache_after_reorg(old_tip, new_header)

            return new_header
        except Exception as e:
            logger.error("Failed to update tip: %s", e)
            return self._current_tip

    def _invalidate_cache_after_reorg(
        self,
        old_tip: Optional[BlockHeader],
        new_tip: Optional[BlockHeader],
    ) -> None:
        """Invalidate cache entries affected by reorganization."""
        if not old_tip or not new_tip:
            return
        if new_tip.height < old_tip.height:
            self._header_cache.clear()
            self._block_cache.clear()

    def subscribe(
        self,
        callback: Callable[[str, int], None],
    ) -> int:
        """Subscribe to new blocks.

        Args:
            callback: Function(block_hash, height)

        Returns:
            Subscription ID
        """
        with self._lock:
            self._subscription_id += 1
            sub_id = self._subscription_id
            self._subscriptions[sub_id] = callback
            self._callbacks_confirmation.append(callback)
            return sub_id

    def unsubscribe(self, subscription_id: int) -> bool:
        """Unsubscribe from notifications.

        Args:
            subscription_id: Subscription ID to remove

        Returns:
            True if subscription was found
        """
        with self._lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                return True
            return False

    def on_new_block(self, callback: Callable[[BlockHeader], None]) -> None:
        """Register callback for new blocks.

        Args:
            callback: Function receiving BlockHeader
        """
        self._callbacks_new_block.append(callback)

    def on_reorg(self, callback: Callable[[ReorgEvent], None]) -> None:
        """Register callback for reorganizations.

        Args:
            callback: Function receiving ReorgEvent
        """
        self._callbacks_reorg.append(callback)

    def on_confirmation(self, callback: Callable[[str, int], None]) -> None:
        """Register callback for transaction confirmations.

        Args:
            callback: Function(txid, confirmations)
        """
        self._callbacks_confirmation.append(callback)

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "header_cache_size": len(self._header_cache),
            "block_cache_size": len(self._block_cache),
        }

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._header_cache.clear()
        self._block_cache.clear()
        logger.info("Block caches cleared")

    def notify_confirmations(self, txid: str, confirmations: int) -> None:
        """Notify subscribers of confirmations.

        Args:
            txid: Transaction ID
            confirmations: Number of confirmations
        """
        for callback in self._callbacks_confirmation:
            try:
                callback(txid, confirmations)
            except Exception as e:
                logger.error("Confirmation callback error: %s", e)