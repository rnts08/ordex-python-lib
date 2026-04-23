"""
UTXO Service for OrdexCoin and OrdexGold.

Provides UTXO management, coin selection, and wallet service for building
transactions via RPC. Supports both ephemeral and persisted wallets.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Dict, Any, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from ordex.rpc.client import RpcClient

logger = logging.getLogger(__name__)


class CoinSelectionStrategy(Enum):
    """Strategy for coin selection."""
    GREEDY = "greedy"
    OPTIMIZED = "optimized"


class WalletPersistence(Enum):
    """Wallet storage mode."""
    EPHEMERAL = "ephemeral"
    DISK = "disk"


@dataclass
class UTXO:
    """Represents an unspent transaction output.

    Attributes:
        txid: Transaction ID (hex string)
        vout: Output index
        amount: Value in satoshis
        script_pubkey: Output script (hex string)
        confirmations: Number of confirmations
        redeem_script: Redeem script for P2SH (if any)
        address: The address controlling this UTXO
        coinbase: Whether this is a coinbase UTXO
        wallet_id: ID of the wallet that owns this UTXO
    """

    txid: str
    vout: int
    amount: int
    script_pubkey: str
    confirmations: int = 0
    redeem_script: Optional[str] = None
    address: Optional[str] = None
    coinbase: bool = False
    wallet_id: str = "default"

    def __post_init__(self) -> None:
        if self.coinbase and self.confirmations < 100:
            self.coinbase = True

    @property
    def outpoint(self) -> tuple:
        return (self.txid, self.vout)

    @property
    def is_spendable(self) -> bool:
        coinbase_maturity = 100 if self.coinbase else 1
        return self.confirmations >= coinbase_maturity

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_rpc(cls, data: Dict[str, Any], wallet_id: str = "default") -> "UTXO":
        return cls(
            txid=data["txid"],
            vout=data["vout"],
            amount=int(Decimal(data["amount"]) * 100_000_000),
            script_pubkey=data.get("scriptPubKey", ""),
            confirmations=data.get("confirmations", 0),
            redeem_script=data.get("redeemScript"),
            address=data.get("address"),
            coinbase=data.get("coinbase", False),
            wallet_id=wallet_id,
        )


@dataclass
class CoinSelectionResult:
    """Result of a coin selection operation."""
    utxos: List[UTXO]
    total_amount: int
    fee: int
    excess: int
    success: bool
    error: Optional[str] = None

    @property
    def effective_amount(self) -> int:
        return self.total_amount - self.fee

    @property
    def can_send(self) -> int:
        return max(0, self.effective_amount - self.excess)


@dataclass
class CoinSelector:
    """Coin selector for UTXO management."""
    strategy: CoinSelectionStrategy = CoinSelectionStrategy.OPTIMIZED
    min_confirmations: int = 1
    max_inputs: Optional[int] = None
    excess_relay_fee: int = 0

    def select(
        self,
        utxos: List[UTXO],
        target_amount: int,
        fee_per_byte: int = 1,
    ) -> CoinSelectionResult:
        spendable = [u for u in utxos if u.is_spendable and u.confirmations >= self.min_confirmations]

        if not spendable:
            return CoinSelectionResult(
                utxos=[], total_amount=0, fee=0, excess=0,
                success=False, error="No spendable UTXOs",
            )

        if self.strategy == CoinSelectionStrategy.GREEDY:
            return self._greedy_select(spendable, target_amount, fee_per_byte)
        return self._optimized_select(spendable, target_amount, fee_per_byte)

    def _greedy_select(
        self, utxos: List[UTXO], target_amount: int, fee_per_byte: int
    ) -> CoinSelectionResult:
        sorted_utxos = sorted(utxos, key=lambda u: u.amount, reverse=True)
        selected = []
        total = 0

        for utxo in sorted_utxos:
            if self.max_inputs and len(selected) >= self.max_inputs:
                break
            selected.append(utxo)
            total += utxo.amount
            if total - target_amount >= self._estimate_fee(len(selected), fee_per_byte):
                break

        return self._create_result(selected, target_amount, fee_per_byte)

    def _optimized_select(
        self, utxos: List[UTXO], target_amount: int, fee_per_byte: int
    ) -> CoinSelectionResult:
        if not utxos:
            return CoinSelectionResult([], 0, 0, 0, False, "No UTXOs")

        sorted_utxos = sorted(utxos, key=lambda u: u.amount)
        best_solution: Optional[List[UTXO]] = None
        best_excess = float('inf')

        def search(idx: int, current_total: int, selected: List[UTXO]) -> None:
            nonlocal best_solution, best_excess

            if len(selected) > (self.max_inputs or len(sorted_utxos)):
                return

            fee = self._estimate_fee(len(selected), fee_per_byte)
            if current_total >= target_amount + fee:
                excess = current_total - target_amount - fee
                if 0 <= excess < best_excess:
                    best_solution = list(selected)
                    best_excess = excess
                return

            if idx >= len(sorted_utxos):
                return

            if current_total + sum(u.amount for u in sorted_utxos[idx:]) < target_amount:
                return

            search(idx + 1, current_total, selected)

            if len(selected) < (self.max_inputs or len(sorted_utxos)):
                selected.append(sorted_utxos[idx])
                search(idx + 1, current_total + sorted_utxos[idx].amount, selected)
                selected.pop()

        search(0, 0, [])

        if best_solution is None:
            return CoinSelectionResult([], 0, 0, 0, False, "Could not find solution")

        return self._create_result(best_solution, target_amount, fee_per_byte)

    def _estimate_fee(self, num_inputs: int, fee_per_byte: int) -> int:
        estimated_size = num_inputs * 148 + 34 + 10
        return (estimated_size + self.excess_relay_fee) * fee_per_byte

    def _create_result(
        self, utxos: List[UTXO], target_amount: int, fee_per_byte: int
    ) -> CoinSelectionResult:
        total = sum(u.amount for u in utxos)
        fee = self._estimate_fee(len(utxos), fee_per_byte)
        excess = total - target_amount - fee

        return CoinSelectionResult(
            utxos=utxos,
            total_amount=total,
            fee=fee,
            excess=max(0, excess),
            success=total >= target_amount + fee,
            error=None if total >= target_amount + fee else "Insufficient funds",
        )


@dataclass
class WalletStats:
    """Statistics for a wallet."""
    wallet_id: str
    total_utxos: int = 0
    total_balance: int = 0
    confirmed_balance: int = 0
    unconfirmed_balance: int = 0
    immature_balance: int = 0
    avg_utxo_value: int = 0
    largest_utxo: int = 0
    smallest_utxo: int = 0
    utxo_count_by_address: Dict[str, int] = field(default_factory=dict)
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"Wallet: {self.wallet_id}\n"
            f"  UTXOs: {self.total_utxos}\n"
            f"  Total Balance: {self.total_balance:,} satoshis\n"
            f"  Confirmed: {self.confirmed_balance:,}\n"
            f"  Unconfirmed: {self.unconfirmed_balance:,}\n"
            f"  Immature: {self.immature_balance:,}\n"
            f"  Largest UTXO: {self.largest_utxo:,}\n"
            f"  Avg UTXO: {self.avg_utxo_value:,}\n"
            f"  Last Updated: {self.last_updated}"
        )


@dataclass
class Wallet:
    """Represents a wallet with UTXOs and metadata."""
    wallet_id: str
    name: str = ""
    utxos: List[UTXO] = field(default_factory=list)
    addresses: List[str] = field(default_factory=list)
    created_at: str = ""
    last_activity: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @property
    def balance(self) -> int:
        return sum(u.amount for u in self.utxos)

    @property
    def spendable_balance(self) -> int:
        return sum(u.amount for u in self.utxos if u.is_spendable)

    @property
    def confirmed_balance(self) -> int:
        return sum(u.amount for u in self.utxos if u.confirmations >= 6)

    def get_stats(self) -> WalletStats:
        confirmed = sum(u.amount for u in self.utxos if u.confirmations >= 6)
        unconfirmed = sum(u.amount for u in self.utxos if 0 < u.confirmations < 6)
        immature = sum(u.amount for u in self.utxos if u.coinbase and u.confirmations < 100)

        amounts = [u.amount for u in self.utxos]

        return WalletStats(
            wallet_id=self.wallet_id,
            total_utxos=len(self.utxos),
            total_balance=self.balance,
            confirmed_balance=confirmed,
            unconfirmed_balance=unconfirmed,
            immature_balance=immature,
            avg_utxo_value=sum(amounts) // len(amounts) if amounts else 0,
            largest_utxo=max(amounts) if amounts else 0,
            smallest_utxo=min(amounts) if amounts else 0,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wallet_id": self.wallet_id,
            "name": self.name,
            "utxos": [u.to_dict() for u in self.utxos],
            "addresses": self.addresses,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "metadata": self.metadata,
        }

    def to_file(self, path: Path) -> None:
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def from_file(cls, path: Path) -> "Wallet":
        with open(path, 'r') as f:
            data = json.load(f)
        data["utxos"] = [UTXO(**u) for u in data.get("utxos", [])]
        return cls(**data)


class WalletManager:
    """Manages multiple wallets with persistence.

    Supports ephemeral (in-memory) and disk-persisted wallets.
    """

    def __init__(
        self,
        rpc_client: "RpcClient",
        storage_path: Optional[Path] = None,
        default_selector: Optional[CoinSelector] = None,
    ) -> None:
        self.rpc = rpc_client
        self.storage_path = storage_path
        self.default_selector = default_selector or CoinSelector(
            strategy=CoinSelectionStrategy.OPTIMIZED
        )
        self._wallets: Dict[str, Wallet] = {}
        self._lock = threading.Lock()
        self._stats: Dict[str, WalletStats] = {}

        if storage_path:
            storage_path.mkdir(parents=True, exist_ok=True)
            self._load_wallets()

    def _load_wallets(self) -> None:
        """Load wallets from disk."""
        if not self.storage_path:
            return
        for f in self.storage_path.glob("wallet_*.json"):
            try:
                wallet = Wallet.from_file(f)
                self._wallets[wallet.wallet_id] = wallet
                logger.info("Loaded wallet: %s", wallet.wallet_id)
            except Exception as e:
                logger.error("Failed to load wallet %s: %s", f, e)

    def _save_wallet(self, wallet: Wallet) -> None:
        """Save wallet to disk."""
        if not self.storage_path:
            return
        wallet.last_activity = datetime.now(timezone.utc).isoformat()
        path = self.storage_path / f"wallet_{wallet.wallet_id}.json"
        wallet.to_file(path)

    def create_wallet(
        self,
        name: str,
        wallet_id: Optional[str] = None,
        addresses: Optional[List[str]] = None,
    ) -> Wallet:
        """Create a new wallet.

        Args:
            name: Wallet name
            wallet_id: Unique ID (auto-generated if not provided)
            addresses: Initial addresses to track

        Returns:
            Created wallet
        """
        with self._lock:
            wid = wallet_id or f"wallet_{len(self._wallets) + 1}"
            if wid in self._wallets:
                raise ValueError(f"Wallet {wid} already exists")

            wallet = Wallet(
                wallet_id=wid,
                name=name,
                addresses=addresses or [],
            )
            self._wallets[wid] = wallet
            self._save_wallet(wallet)
            return wallet

    def get_wallet(self, wallet_id: str) -> Optional[Wallet]:
        """Get a wallet by ID."""
        return self._wallets.get(wallet_id)

    def delete_wallet(self, wallet_id: str) -> bool:
        """Delete a wallet."""
        with self._lock:
            if wallet_id not in self._wallets:
                return False
            del self._wallets[wallet_id]
            if self.storage_path:
                path = self.storage_path / f"wallet_{wallet_id}.json"
                if path.exists():
                    path.unlink()
            return True

    def list_wallets(self) -> List[str]:
        """List all wallet IDs."""
        return list(self._wallets.keys())

    def sync_wallet(self, wallet_id: str, force: bool = False) -> WalletStats:
        """Sync wallet UTXOs from RPC node.

        Args:
            wallet_id: Wallet to sync
            force: Ignore cache and force refresh

        Returns:
            Wallet statistics
        """
        wallet = self._wallets.get(wallet_id)
        if not wallet:
            raise ValueError(f"Wallet {wallet_id} not found")

        try:
            result = self.rpc.listunspent(
                minconf=0,
                addresses=wallet.addresses if wallet.addresses else None,
            )
            wallet.utxos = [
                UTXO.from_rpc(u, wallet_id) for u in result
            ]
            wallet.last_activity = datetime.now(timezone.utc).isoformat()
            stats = wallet.get_stats()
            self._stats[wallet_id] = stats

            if not force and self.storage_path:
                self._save_wallet(wallet)

            return stats

        except Exception as e:
            logger.error("Failed to sync wallet %s: %s", wallet_id, e)
            return self._stats.get(wallet_id, WalletStats(wallet_id=wallet_id))

    def sync_all(self) -> Dict[str, WalletStats]:
        """Sync all wallets."""
        return {
            wid: self.sync_wallet(wid)
            for wid in self._wallets
        }

    def get_stats(self, wallet_id: str) -> Optional[WalletStats]:
        """Get cached stats for a wallet."""
        return self._stats.get(wallet_id)

    def get_all_stats(self) -> Dict[str, WalletStats]:
        """Get stats for all wallets."""
        return dict(self._stats)

    def select_coins(
        self,
        wallet_id: str,
        amount: int,
        fee_per_byte: int = 1,
        strategy: Optional[CoinSelectionStrategy] = None,
    ) -> CoinSelectionResult:
        """Select UTXOs from a wallet.

        Args:
            wallet_id: Wallet to select from
            amount: Target amount in satoshis
            fee_per_byte: Fee rate
            strategy: Selection strategy

        Returns:
            Coin selection result
        """
        if wallet_id not in self._stats:
            self.sync_wallet(wallet_id)

        wallet = self._wallets.get(wallet_id)
        if not wallet:
            return CoinSelectionResult([], 0, 0, 0, False, "Wallet not found")

        selector = CoinSelector(strategy=strategy or self.default_selector.strategy)
        return selector.select(wallet.utxos, amount, fee_per_byte)

    def get_balance(self, wallet_id: str, min_confirmations: int = 1) -> int:
        """Get wallet balance."""
        wallet = self._wallets.get(wallet_id)
        if not wallet:
            return 0
        if min_confirmations == 0:
            return wallet.balance
        if min_confirmations == 6:
            return wallet.confirmed_balance
        return sum(
            u.amount for u in wallet.utxos
            if u.confirmations >= min_confirmations
        )

    def add_address(self, wallet_id: str, address: str) -> bool:
        """Add an address to a wallet."""
        wallet = self._wallets.get(wallet_id)
        if not wallet:
            return False
        if address not in wallet.addresses:
            wallet.addresses.append(address)
            self._save_wallet(wallet)
        return True

    def generate_address(self, wallet_id: str, address_type: str = "") -> Optional[str]:
        """Generate a new address for a wallet."""
        wallet = self._wallets.get(wallet_id)
        if not wallet:
            return None
        try:
            address = self.rpc.getnewaddress(address_type)
            wallet.addresses.append(address)
            self._save_wallet(wallet)
            return address
        except Exception as e:
            logger.error("Failed to generate address: %s", e)
            return None

    def full_stats_report(self) -> str:
        """Generate a full statistics report."""
        lines = ["=" * 50, "WALLET MANAGER REPORT", "=" * 50, ""]

        for wid in self._wallets:
            stats = self._stats.get(wid)
            wallet = self._wallets.get(wid)
            if stats:
                lines.append(stats.summary())
                lines.append("")
            else:
                lines.append(f"Wallet: {wid}")
                if wallet and wallet.name:
                    lines.append(f"  Name: {wallet.name}")
                lines.append("  No stats available (run sync)")
                lines.append("")

        total_utxos = sum(s.total_utxos for s in self._stats.values())
        total_balance = sum(s.total_balance for s in self._stats.values())

        lines.append("-" * 50)
        lines.append(f"TOTAL UTXOs: {total_utxos}")
        lines.append(f"TOTAL BALANCE: {total_balance:,} satoshis")
        lines.append("=" * 50)

        return "\n".join(lines)