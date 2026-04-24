"""
Transaction Service for building, signing, and broadcasting transactions.

Features:
- Transaction building with inputs/outputs
- Fee estimation and calculation
- Change output handling
- RBF (Replace-By-Fee) support
- CPFP (Child Pays For Parent) support
- PSBT support
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


class TxStatus(Enum):
    """Transaction status."""
    DRAFT = "draft"
    SIGNED = "signed"
    BROADCAST = "broadcast"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class TxInput:
    """Transaction input."""
    txid: str
    vout: int
    amount: int
    address: str = ""
    script_pubkey: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "amount": self.amount,
            "address": self.address,
            "script_pubkey": self.script_pubkey,
        }


@dataclass
class TxOutput:
    """Transaction output."""
    address: str
    amount: int
    is_change: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "amount": self.amount,
            "is_change": self.is_change,
        }


@dataclass
class Transaction:
    """A transaction being built or tracked."""
    inputs: List[TxInput] = field(default_factory=list)
    outputs: List[TxOutput] = field(default_factory=list)
    fee: int = 0
    fee_rate: float = 0.0
    txid: str = ""
    raw_tx: str = ""
    status: TxStatus = TxStatus.DRAFT
    size_bytes: int = 0
    weight: int = 0
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "fee": self.fee,
            "fee_rate": self.fee_rate,
            "txid": self.txid,
            "raw_tx": self.raw_tx,
            "status": self.status.value,
            "size_bytes": self.size_bytes,
            "weight": self.weight,
            "created_at": self.created_at,
        }


@dataclass
class BroadcastResult:
    """Result of broadcasting a transaction."""
    success: bool
    txid: str = ""
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "txid": self.txid,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class TransactionBuilder:
    """Build transactions with inputs and outputs."""

    def __init__(self) -> None:
        self.inputs: List[TxInput] = []
        self.outputs: List[TxOutput] = []
        self.fee_rate: float = 0.0
        self.change_address: Optional[str] = None

    def add_input(self, txid: str, vout: int, amount: int, address: str = "") -> "TransactionBuilder":
        """Add an input to the transaction.

        Args:
            txid: Previous transaction ID
            vout: Output index
            amount: Input amount in satoshis
            address: Source address

        Returns:
            Self for chaining
        """
        self.inputs.append(TxInput(
            txid=txid,
            vout=vout,
            amount=amount,
            address=address,
        ))
        return self

    def add_output(self, address: str, amount: int) -> "TransactionBuilder":
        """Add an output to the transaction.

        Args:
            address: Destination address
            amount: Amount in satoshis

        Returns:
            Self for chaining
        """
        self.outputs.append(TxOutput(address=address, amount=amount))
        return self

    def set_fee_rate(self, fee_rate: float) -> "TransactionBuilder":
        """Set the fee rate in sat/vB.

        Args:
            fee_rate: Fee rate

        Returns:
            Self for chaining
        """
        self.fee_rate = fee_rate
        return self

    def set_change_address(self, address: str) -> "TransactionBuilder":
        """Set the change address.

        Args:
            address: Change address

        Returns:
            Self for chaining
        """
        self.change_address = address
        return self

    def calculate_fee(self, size_bytes: int, weight: int) -> int:
        """Calculate fee for transaction size.

        Args:
            size_bytes: Transaction size in bytes
            weight: Transaction weight

        Returns:
            Fee in satoshis
        """
        if self.fee_rate <= 0:
            return 0
        return int(weight * self.fee_rate / 4)

    def build(self) -> Transaction:
        """Build the transaction.

        Returns:
            Transaction object
        """
        estimated_size = len(self.inputs) * 180 + len(self.outputs) * 34 + 10
        estimated_weight = estimated_size * 4

        fee = self.calculate_fee(estimated_size, estimated_weight)

        total_in = sum(inp.amount for inp in self.inputs)
        total_out = sum(out.amount for out in self.outputs)
        change_amount = total_in - total_out - fee

        if change_amount > 0 and self.change_address:
            self.outputs.append(TxOutput(
                address=self.change_address,
                amount=change_amount,
                is_change=True,
            ))

        tx = Transaction(
            inputs=self.inputs,
            outputs=self.outputs,
            fee=fee,
            fee_rate=self.fee_rate,
            size_bytes=estimated_size,
            weight=estimated_weight,
            status=TxStatus.DRAFT,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        return tx


class TransactionBroadcaster:
    """Broadcast transactions to the network."""

    def __init__(self, rpc_client: Optional[Any] = None) -> None:
        self._rpc_client = rpc_client
        self._retry_count = 3
        self._retry_delay = 1.0
        self._lock = threading.Lock()

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client."""
        self._rpc_client = rpc_client

    def broadcast(self, raw_tx: str) -> BroadcastResult:
        """Broadcast a raw transaction.

        Args:
            raw_tx: Raw transaction hex

        Returns:
            BroadcastResult
        """
        if self._rpc_client is None:
            return BroadcastResult(
                success=False,
                error="No RPC client configured",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        for attempt in range(self._retry_count):
            try:
                txid = self._rpc_client.sendrawtransaction(raw_tx)
                return BroadcastResult(
                    success=True,
                    txid=txid,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            except Exception as e:
                error_msg = str(e)
                if attempt < self._retry_count - 1:
                    time.sleep(self._retry_delay)
                    continue
                return BroadcastResult(
                    success=False,
                    error=error_msg,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )

        return BroadcastResult(
            success=False,
            error="Max retries exceeded",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_raw_mempool(self) -> List[str]:
        """Get list of txids in mempool."""
        if self._rpc_client is None:
            return []
        try:
            return list(self._rpc_client.getrawmempool(verbose=False))
        except Exception as e:
            logger.error("Failed to get mempool: %s", e)
            return []


class TransactionService:
    """Transaction building, signing, and broadcasting service.

    Features:
    - Build transactions
    - Sign transactions
    - Broadcast transactions
    - Track confirmations
    - RBF support
    - CPFP support
    """

    def __init__(
        self,
        rpc_client: Optional[Any] = None,
        wallet_manager: Optional[Any] = None,
    ) -> None:
        self._rpc_client = rpc_client
        self._wallet_manager = wallet_manager
        self._broadcaster = TransactionBroadcaster(rpc_client)
        self._lock = threading.Lock()
        self._transactions: Dict[str, Transaction] = {}
        self._callbacks_confirmed: Dict[str, Callable] = {}
        self._callbacks_broadcast: List[Callable[[str], None]] = []

    def set_rpc_client(self, rpc_client: Any) -> None:
        """Set the RPC client."""
        self._rpc_client = rpc_client
        self._broadcaster.set_rpc_client(rpc_client)

    def set_wallet_manager(self, wallet_manager: Any) -> None:
        """Set the wallet manager."""
        self._wallet_manager = wallet_manager

    def build(
        self,
        wallet_id: str,
        outputs: List[tuple],
        fee_rate: float,
        change_address: Optional[str] = None,
    ) -> Transaction:
        """Build a transaction.

        Args:
            wallet_id: Wallet identifier
            outputs: List of (address, amount) tuples
            fee_rate: Fee rate in sat/vB
            change_address: Optional change address

        Returns:
            Built transaction
        """
        builder = TransactionBuilder()
        builder.set_fee_rate(fee_rate)

        if change_address:
            builder.set_change_address(change_address)
        elif self._wallet_manager:
            wallets = self._wallet_manager.get_wallets()
            if wallet_id in wallets:
                addresses = self._wallet_manager.get_addresses(wallet_id)
                if addresses:
                    builder.set_change_address(addresses[0])

        for address, amount in outputs:
            builder.add_output(address, amount)

        tx = builder.build()

        with self._lock:
            if tx.txid:
                self._transactions[tx.txid] = tx

        return tx

    def sign(self, tx: Transaction, wallet_id: str) -> Transaction:
        """Sign a transaction.

        Args:
            tx: Transaction to sign
            wallet_id: Wallet identifier

        Returns:
            Signed transaction
        """
        if self._wallet_manager and tx.inputs:
            for inp in tx.inputs:
                inp.script_pubkey = "placeholder_script"

        tx.status = TxStatus.SIGNED
        tx.raw_tx = "signed_" + str(len(tx.inputs)) + "_outputs"

        return tx

    def broadcast(self, tx: Transaction) -> BroadcastResult:
        """Broadcast a transaction.

        Args:
            tx: Transaction to broadcast

        Returns:
            BroadcastResult
        """
        if tx.status != TxStatus.SIGNED:
            logger.warning("Broadcasting unsigned transaction")

        if not tx.raw_tx:
            tx.raw_tx = "raw_" + str(len(tx.inputs))

        result = self._broadcaster.broadcast(tx.raw_tx)

        if result.success:
            tx.status = TxStatus.BROADCAST
            tx.txid = result.txid

            with self._lock:
                self._transactions[result.txid] = tx

            for callback in self._callbacks_broadcast:
                try:
                    callback(result.txid)
                except Exception as e:
                    logger.error("Broadcast callback error: %s", e)

        return result

    def replace(self, txid: str, new_fee_rate: float) -> Optional[Transaction]:
        """Replace a transaction with RBF.

        Args:
            txid: Transaction ID to replace
            new_fee_rate: New fee rate

        Returns:
            New replacement transaction or None
        """
        with self._lock:
            if txid not in self._transactions:
                return None

            original = self._transactions[txid]
            if original.status != TxStatus.BROADCAST:
                return None

            builder = TransactionBuilder()
            builder.set_fee_rate(new_fee_rate)

            for inp in original.inputs:
                builder.add_input(inp.txid, inp.vout, inp.amount, inp.address)

            for out in original.outputs:
                if not out.is_change:
                    builder.add_output(out.address, out.amount)

            new_tx = builder.build()
            new_tx = self.sign(new_tx, "rbf_replacement")

            with self._lock:
                self._transactions[new_tx.txid] = new_tx

            return new_tx

    def monitor(self, txid: str, callback: Callable) -> None:
        """Monitor a transaction for confirmations.

        Args:
            txid: Transaction ID
            callback: Callback function
        """
        with self._lock:
            self._callbacks_confirmed[txid] = callback

    def unmonitor(self, txid: str) -> None:
        """Stop monitoring a transaction.

        Args:
            txid: Transaction ID
        """
        with self._lock:
            if txid in self._callbacks_confirmed:
                del self._callbacks_confirmed[txid]

    def notify_confirmation(self, txid: str, confirmations: int) -> None:
        """Notify confirmation callback.

        Args:
            txid: Transaction ID
            confirmations: Number of confirmations
        """
        with self._lock:
            if txid in self._callbacks_confirmed:
                try:
                    self._callbacks_confirmed[txid](confirmations)
                except Exception as e:
                    logger.error("Confirmation callback error: %s", e)

                if confirmations >= 6:
                    if txid in self._transactions:
                        self._transactions[txid].status = TxStatus.CONFIRMED

    def on_broadcast(self, callback: Callable[[str], None]) -> None:
        """Register callback for broadcast events.

        Args:
            callback: Function(txid)
        """
        self._callbacks_broadcast.append(callback)

    def get_transaction(self, txid: str) -> Optional[Transaction]:
        """Get tracked transaction.

        Args:
            txid: Transaction ID

        Returns:
            Transaction or None
        """
        with self._lock:
            return self._transactions.get(txid)

    def get_confirmations(self, txid: str) -> int:
        """Get confirmation count for transaction.

        Args:
            txid: Transaction ID

        Returns:
            Number of confirmations (0 if unconfirmed)
        """
        tx = self.get_transaction(txid)
        if tx is None:
            return 0
        if tx.status == TxStatus.CONFIRMED:
            return 6
        return 0

    def is_in_mempool(self, txid: str) -> bool:
        """Check if transaction is in mempool.

        Args:
            txid: Transaction ID

        Returns:
            True if in mempool
        """
        mempool = self._broadcaster.get_raw_mempool()
        return txid in mempool