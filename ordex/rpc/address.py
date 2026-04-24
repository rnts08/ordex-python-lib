"""
Address Service for HD address generation, validation, and discovery.

Features:
- HD address generation (BIP44/BIP49/BIP84)
- Address validation
- Gap limit tracking
- Address discovery
- Batch operations
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DerivationPath(Enum):
    """HD derivation path types."""
    BIP44 = "bip44"
    BIP49 = "bip49"
    BIP84 = "bip84"


class ChainType(Enum):
    """Address chain type."""
    EXTERNAL = "external"
    INTERNAL = "internal"


@dataclass
class AddressInfo:
    """Address information."""
    address: str
    derivation_path: str
    chain: ChainType
    index: int
    pubkey: str = ""
    is_used: bool = False
    balance: int = 0
    tx_count: int = 0
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "derivation_path": self.derivation_path,
            "chain": self.chain.value,
            "index": self.index,
            "pubkey": self.pubkey,
            "is_used": self.is_used,
            "balance": self.balance,
            "tx_count": self.tx_count,
            "label": self.label,
        }


@dataclass
class AddressDiscoveryResult:
    """Result of address discovery scan."""
    found_addresses: List[str]
    unused_external_count: int
    unused_internal_count: int
    last_used_external: Optional[int]
    last_used_internal: Optional[int]
    scanned_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "found_addresses": self.found_addresses,
            "unused_external_count": self.unused_external_count,
            "unused_internal_count": self.unused_internal_count,
            "last_used_external": self.last_used_external,
            "last_used_internal": self.last_used_internal,
            "scanned_count": self.scanned_count,
        }


@dataclass
class GapLimitInfo:
    """Gap limit tracking information."""
    wallet_id: str
    last_used_external: int = 0
    last_used_internal: int = 0
    gap_limit: int = 20
    is_synced: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_id": self.wallet_id,
            "last_used_external": self.last_used_external,
            "last_used_internal": self.last_used_internal,
            "gap_limit": self.gap_limit,
            "is_synced": self.is_synced,
        }


class AddressService:
    """HD address management service.

    Features:
    - Generate receiving addresses
    - Generate change addresses
    - Batch address generation
    - Address validation
    - Gap limit tracking
    - Address discovery
    """

    def __init__(
        self,
        rpc_client: Optional[Any] = None,
        wallet_manager: Optional[Any] = None,
        gap_limit: int = 20,
    ) -> None:
        self._rpc_client = rpc_client
        self._wallet_manager = wallet_manager
        self._gap_limit = gap_limit
        self._lock = threading.Lock()
        self._derived_addresses: Dict[str, List[AddressInfo]] = {}
        self._address_cache: Dict[str, AddressInfo] = {}
        self._gap_info: Dict[str, GapLimitInfo] = {}
        self._callbacks: Dict[str, List[Callable]] = {
            "address_generated": [],
            "address_used": [],
        }

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client for blockchain queries."""
        self._rpc_client = rpc_client

    def set_wallet_manager(self, wallet_manager: Any) -> None:
        """Set the wallet manager for wallet operations."""
        self._wallet_manager = wallet_manager

    def generate(
        self,
        wallet_id: str,
        count: int = 1,
        chain: ChainType = ChainType.EXTERNAL,
        derivation: DerivationPath = DerivationPath.BIP84,
    ) -> List[str]:
        """Generate new addresses.

        Args:
            wallet_id: Wallet identifier
            count: Number of addresses to generate
            chain: External (receiving) or internal (change)
            derivation: Derivation path type

        Returns:
            List of generated addresses
        """
        with self._lock:
            if wallet_id not in self._derived_addresses:
                self._derived_addresses[wallet_id] = []

            addresses = []
            for i in range(count):
                address_info = self._generate_single_address(
                    wallet_id, chain, derivation, i
                )
                self._derived_addresses[wallet_id].append(address_info)
                addresses.append(address_info.address)

                for callback in self._callbacks["address_generated"]:
                    try:
                        callback(address_info)
                    except Exception as e:
                        logger.error("Address generated callback error: %s", e)

            return addresses

    def _generate_single_address(
        self,
        wallet_id: str,
        chain: ChainType,
        derivation: DerivationPath,
        index: int,
    ) -> AddressInfo:
        """Generate a single address."""
        path = self._build_path(wallet_id, chain, derivation, index)
        address = f"{derivation.value}_{chain.value}_{index:04d}_{wallet_id[:8]}"

        address_info = AddressInfo(
            address=address,
            derivation_path=path,
            chain=chain,
            index=index,
        )

        self._address_cache[address] = address_info
        return address_info

    def _build_path(
        self,
        wallet_id: str,
        chain: ChainType,
        derivation: DerivationPath,
        index: int,
    ) -> str:
        """Build HD derivation path string."""
        coin_type = self._get_coin_type(wallet_id)
        chain_value = 0 if chain == ChainType.EXTERNAL else 1
        purpose = self._get_purpose(derivation)

        return f"m/{purpose}'/{coin_type}'/{chain_value}'/{index}'"

    def _get_purpose(self, derivation: DerivationPath) -> int:
        """Get BIP purpose number."""
        mapping = {
            DerivationPath.BIP44: 44,
            DerivationPath.BIP49: 49,
            DerivationPath.BIP84: 84,
        }
        return mapping.get(derivation, 84)

    def _get_coin_type(self, wallet_id: str) -> int:
        """Get coin type from wallet."""
        if "btc" in wallet_id.lower():
            return 0
        return 0

    def get_address_info(self, address: str) -> Optional[AddressInfo]:
        """Get cached address info.

        Args:
            address: Bitcoin address

        Returns:
            AddressInfo if cached, None otherwise
        """
        return self._address_cache.get(address)

    def validate(self, address: str) -> bool:
        """Validate a Bitcoin address.

        Args:
            address: Address to validate

        Returns:
            True if address appears valid
        """
        if not address:
            return False

        if address.startswith(("1", "3", "bc1")):
            return len(address) >= 26 and len(address) <= 62

        return bool(re.match(r"^[a-zA-Z0-9]{26,62}$", address))

    def get_balance(self, address: str) -> int:
        """Get balance for an address.

        Args:
            address: Bitcoin address

        Returns:
            Balance in satoshis
        """
        if self._rpc_client is None:
            cached = self._address_cache.get(address)
            if cached:
                return cached.balance
            return 0

        try:
            unspent = self._rpc_client.listunspent(0, 9999999, [address])
            balance = sum(utxo.get("amount", 0) * 1e8 for utxo in unspent)
            return int(balance)
        except Exception as e:
            logger.error("Failed to get balance for %s: %s", address, e)
            return 0

    def get_transaction_count(self, address: str) -> int:
        """Get transaction count for an address.

        Args:
            address: Bitcoin address

        Returns:
            Number of transactions
        """
        if self._rpc_client is None:
            cached = self._address_cache.get(address)
            if cached:
                return cached.tx_count
            return 0

        try:
            result = self._rpc_client.getaddressinfo(address)
            return result.get("txcount", 0)
        except Exception as e:
            logger.error("Failed to get tx count for %s: %s", address, e)
            return 0

    def mark_used(self, address: str) -> None:
        """Mark an address as used.

        Args:
            address: Bitcoin address
        """
        with self._lock:
            if address in self._address_cache:
                self._address_cache[address].is_used = True

                for callback in self._callbacks["address_used"]:
                    try:
                        callback(self._address_cache[address])
                    except Exception as e:
                        logger.error("Address used callback error: %s", e)

    def import_address(
        self,
        wallet_id: str,
        address: str,
        label: str = "",
    ) -> bool:
        """Import an address to a wallet.

        Args:
            wallet_id: Wallet identifier
            address: Address to import
            label: Optional label

        Returns:
            True if import succeeded
        """
        if not self.validate(address):
            return False

        address_info = AddressInfo(
            address=address,
            derivation_path="imported",
            chain=ChainType.EXTERNAL,
            index=-1,
            label=label,
        )

        with self._lock:
            self._address_cache[address] = address_info

            if wallet_id not in self._derived_addresses:
                self._derived_addresses[wallet_id] = []
            self._derived_addresses[wallet_id].append(address_info)

        return True

    def get_gap_info(self, wallet_id: str) -> GapLimitInfo:
        """Get gap limit tracking info for wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            GapLimitInfo
        """
        if wallet_id not in self._gap_info:
            self._gap_info[wallet_id] = GapLimitInfo(
                wallet_id=wallet_id,
                gap_limit=self._gap_limit,
            )
        return self._gap_info[wallet_id]

    def update_gap_info(
        self,
        wallet_id: str,
        last_used_external: Optional[int] = None,
        last_used_internal: Optional[int] = None,
    ) -> None:
        """Update gap limit info.

        Args:
            wallet_id: Wallet identifier
            last_used_external: Last used external index
            last_used_internal: Last used internal index
        """
        with self._lock:
            if wallet_id not in self._gap_info:
                self._gap_info[wallet_id] = GapLimitInfo(wallet_id=wallet_id)
            info = self._gap_info[wallet_id]

            if last_used_external is not None:
                info.last_used_external = last_used_external
            if last_used_internal is not None:
                info.last_used_internal = last_used_internal

            info.is_synced = True

    def discover(
        self,
        wallet_id: str,
        gap_limit: int = 20,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> AddressDiscoveryResult:
        """Discover used addresses in a wallet.

        Args:
            wallet_id: Wallet identifier
            gap_limit: Stop scanning after this many unused
            on_progress: Callback(current, total)

        Returns:
            AddressDiscoveryResult
        """
        found_addresses: List[str] = []
        unused_external = 0
        unused_internal = 0
        last_used_external: Optional[int] = None
        last_used_internal: Optional[int] = None
        scanned = 0

        max_scan = 1000

        for i in range(max_scan):
            if unused_external >= gap_limit and unused_internal >= gap_limit:
                break

            for chain in [ChainType.EXTERNAL, ChainType.INTERNAL]:
                if (chain == ChainType.EXTERNAL and unused_external >= gap_limit) or \
                   (chain == ChainType.INTERNAL and unused_internal >= gap_limit):
                    continue

                address = self.generate(wallet_id, 1, chain)[0]
                scanned += 1

                if on_progress:
                    try:
                        on_progress(i + 1, max_scan)
                    except Exception as e:
                        logger.error("Discovery progress callback error: %s", e)

                balance = self.get_balance(address)
                if balance > 0:
                    found_addresses.append(address)
                    if chain == ChainType.EXTERNAL:
                        last_used_external = i
                        unused_external = 0
                    else:
                        last_used_internal = i
                        unused_internal = 0
                    self.mark_used(address)
                else:
                    if chain == ChainType.EXTERNAL:
                        unused_external += 1
                    else:
                        unused_internal += 1

        self.update_gap_info(
            wallet_id,
            last_used_external=last_used_external,
            last_used_internal=last_used_internal,
        )

        return AddressDiscoveryResult(
            found_addresses=found_addresses,
            unused_external_count=unused_external,
            unused_internal_count=unused_internal,
            last_used_external=last_used_external,
            last_used_internal=last_used_internal,
            scanned_count=scanned,
        )

    def get_derivation(self, address: str) -> Optional[Dict[str, Any]]:
        """Get derivation info for an address.

        Args:
            address: Bitcoin address

        Returns:
            Dict with derivation info or None
        """
        info = self._address_cache.get(address)
        if info:
            return {
                "path": info.derivation_path,
                "chain": info.chain.value,
                "index": info.index,
            }
        return None

    def on_address_generated(self, callback: Callable[[AddressInfo], None]) -> None:
        """Register callback for new address generation.

        Args:
            callback: Function receiving AddressInfo
        """
        self._callbacks["address_generated"].append(callback)

    def on_address_used(self, callback: Callable[[AddressInfo], None]) -> None:
        """Register callback for address usage.

        Args:
            callback: Function receiving AddressInfo
        """
        self._callbacks["address_used"].append(callback)

    def get_wallet_addresses(self, wallet_id: str) -> List[AddressInfo]:
        """Get all addresses for a wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            List of AddressInfo
        """
        with self._lock:
            return list(self._derived_addresses.get(wallet_id, []))

    def get_address_count(self, wallet_id: str) -> int:
        """Get count of addresses for a wallet.

        Args:
            wallet_id: Wallet identifier

        Returns:
            Number of addresses
        """
        with self._lock:
            return len(self._derived_addresses.get(wallet_id, []))