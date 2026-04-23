"""
Transaction primitives for OrdexCoin and OrdexGold.

Implements COutPoint, CTxIn, CTxOut, CTransaction, and CMutableTransaction
with full SegWit serialization support.  OrdexGold's MWEB transaction flag
(0x08) is handled by storing MWEB data as an opaque blob.
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO, List, Optional

from ordex.core.hash import sha256d
from ordex.core.script import CScript
from ordex.core.serialize import (
    read_compact_size, write_compact_size,
    read_int32, write_int32,
    read_uint32, write_uint32,
    read_int64,
    read_hash256, write_hash256,
    read_string, write_string,
    read_bytes,
)

# Flag OR'd into serialization version to omit witness data.
SERIALIZE_TRANSACTION_NO_WITNESS = 0x40000000
# Flag OR'd into serialization version to omit MWEB data. (OXG only)
SERIALIZE_NO_MWEB = 0x20000000


class COutPoint:
    """Reference to a specific output of a previous transaction."""

    NULL_INDEX = 0xFFFFFFFF

    __slots__ = ("hash", "n")

    def __init__(self, hash: bytes = b"\x00" * 32, n: int = NULL_INDEX) -> None:
        self.hash = hash
        self.n = n

    def is_null(self) -> bool:
        return self.hash == b"\x00" * 32 and self.n == self.NULL_INDEX

    def serialize(self, f: BinaryIO) -> None:
        write_hash256(f, self.hash)
        write_uint32(f, self.n)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "COutPoint":
        h = read_hash256(f)
        n = read_uint32(f)
        return cls(h, n)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, COutPoint):
            return self.hash == other.hash and self.n == other.n
        return NotImplemented

    def __repr__(self) -> str:
        return f"COutPoint({self.hash[:4].hex()}..., {self.n})"


class CTxIn:
    """Transaction input: references a previous output and provides a signature."""

    SEQUENCE_FINAL = 0xFFFFFFFF
    SEQUENCE_LOCKTIME_DISABLE_FLAG = 1 << 31
    SEQUENCE_LOCKTIME_TYPE_FLAG = 1 << 22
    SEQUENCE_LOCKTIME_MASK = 0x0000FFFF

    __slots__ = ("prevout", "script_sig", "sequence", "script_witness")

    def __init__(
        self,
        prevout: Optional[COutPoint] = None,
        script_sig: bytes = b"",
        sequence: int = SEQUENCE_FINAL,
    ) -> None:
        self.prevout = prevout or COutPoint()
        self.script_sig = CScript(script_sig)
        self.sequence = sequence
        self.script_witness: List[bytes] = []  # populated during witness deserialization

    def serialize(self, f: BinaryIO) -> None:
        self.prevout.serialize(f)
        write_string(f, self.script_sig)
        write_uint32(f, self.sequence)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "CTxIn":
        prevout = COutPoint.deserialize(f)
        script_sig = read_string(f)
        sequence = read_uint32(f)
        return cls(prevout, script_sig, sequence)

    def __repr__(self) -> str:
        return f"CTxIn({self.prevout}, seq={self.sequence:#x})"


class CTxOut:
    """Transaction output: an amount and a locking script."""

    __slots__ = ("value", "script_pubkey")

    def __init__(self, value: int = -1, script_pubkey: bytes = b"") -> None:
        self.value = value
        self.script_pubkey = CScript(script_pubkey)

    def is_null(self) -> bool:
        return self.value == -1

    def serialize(self, f: BinaryIO) -> None:
        f.write(self.value.to_bytes(8, "little", signed=True))
        write_string(f, self.script_pubkey)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "CTxOut":
        value = int.from_bytes(read_bytes(f, 8), "little", signed=True)
        script_pubkey = read_string(f)
        return cls(value, script_pubkey)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CTxOut):
            return self.value == other.value and self.script_pubkey == other.script_pubkey
        return NotImplemented

    def __repr__(self) -> str:
        return f"CTxOut(value={self.value}, script={self.script_pubkey[:10].hex()}...)"


class CTransaction:
    """An immutable Bitcoin/Ordex transaction with optional SegWit and MWEB data.

    Serialization format:
      Basic: [nVersion][vin][vout][nLockTime]
      SegWit: [nVersion][0x00][flags][vin][vout][witness...][nLockTime]
      MWEB (OXG): flag bit 0x08 indicates MWEB data follows witness

    The MWEB transaction body is stored as opaque bytes (``mweb_tx_data``).
    """

    __slots__ = (
        "version", "vin", "vout", "locktime",
        "mweb_tx_data", "is_hogex",
        "_hash", "_whash",
    )

    CURRENT_VERSION = 2

    def __init__(
        self,
        version: int = CURRENT_VERSION,
        vin: Optional[List[CTxIn]] = None,
        vout: Optional[List[CTxOut]] = None,
        locktime: int = 0,
        mweb_tx_data: bytes = b"",
        is_hogex: bool = False,
    ) -> None:
        self.version = version
        self.vin = vin or []
        self.vout = vout or []
        self.locktime = locktime
        self.mweb_tx_data = mweb_tx_data
        self.is_hogex = is_hogex
        self._hash: Optional[bytes] = None
        self._whash: Optional[bytes] = None

    # -- Serialization ------------------------------------------------------

    def serialize(self, f: BinaryIO, *, allow_witness: bool = True, allow_mweb: bool = False) -> None:
        write_int32(f, self.version)

        flags = 0
        if allow_witness and self.has_witness():
            flags |= 1
        if allow_mweb and (self.mweb_tx_data or self.is_hogex):
            flags |= 8

        if flags:
            # Extended format: empty vin marker + flags byte
            write_compact_size(f, 0)  # dummy empty vin
            f.write(bytes([flags]))

        # vin
        write_compact_size(f, len(self.vin))
        for txin in self.vin:
            txin.serialize(f)

        # vout
        write_compact_size(f, len(self.vout))
        for txout in self.vout:
            txout.serialize(f)

        # witness data
        if flags & 1:
            for txin in self.vin:
                write_compact_size(f, len(txin.script_witness))
                for item in txin.script_witness:
                    write_string(f, item)

        # MWEB data
        if flags & 8:
            f.write(self.mweb_tx_data)

        write_uint32(f, self.locktime)

    @classmethod
    def deserialize(cls, f: BinaryIO, *, allow_witness: bool = True, allow_mweb: bool = False) -> "CTransaction":
        version = read_int32(f)
        flags = 0

        # Read vin — may be dummy (empty) for extended format
        vin_list: List[CTxIn] = []
        vin_count = read_compact_size(f)
        if vin_count == 0 and allow_witness:
            # Extended format: read flags byte
            flags = read_bytes(f, 1)[0]
            if flags != 0:
                vin_count = read_compact_size(f)

        for _ in range(vin_count):
            vin_list.append(CTxIn.deserialize(f))

        # Read vout
        vout_count = read_compact_size(f)
        vout_list = [CTxOut.deserialize(f) for _ in range(vout_count)]

        # Witness
        if (flags & 1) and allow_witness:
            for txin in vin_list:
                wit_count = read_compact_size(f)
                txin.script_witness = [read_string(f) for _ in range(wit_count)]

        # MWEB
        mweb_tx_data = b""
        is_hogex = False
        locktime = 0
        if (flags & 8) and allow_mweb:
            # Read all remaining bytes (MWEB data + locktime)
            # Format: [mweb_tx_data][locktime: 4 bytes]
            remaining = f.read()
            if remaining and len(remaining) >= 4:
                # Last 4 bytes are locktime, rest is mweb data
                mweb_tx_data = remaining[:-4]
                locktime = int.from_bytes(remaining[-4:], "little")
                is_hogex = len(mweb_tx_data) > 0
            elif remaining:
                # Edge case: only locktime, no MWEB data
                locktime = int.from_bytes(remaining, "little")
                mweb_tx_data = b""
                is_hogex = False
        else:
            # No MWEB, just read locktime normally
            locktime = read_uint32(f)

        return cls(
            version=version,
            vin=vin_list,
            vout=vout_list,
            locktime=locktime,
            mweb_tx_data=mweb_tx_data,
            is_hogex=is_hogex,
        )

    def to_bytes(self, *, allow_witness: bool = True, allow_mweb: bool = False) -> bytes:
        buf = BytesIO()
        self.serialize(buf, allow_witness=allow_witness, allow_mweb=allow_mweb)
        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes, *, allow_witness: bool = True, allow_mweb: bool = False) -> "CTransaction":
        return cls.deserialize(BytesIO(data), allow_witness=allow_witness, allow_mweb=allow_mweb)

    # -- Hashing ------------------------------------------------------------

    def txid(self) -> bytes:
        """Transaction ID (hash without witness data, little-endian internal order)."""
        if self._hash is None:
            self._hash = sha256d(self.to_bytes(allow_witness=False))
        return self._hash

    def wtxid(self) -> bytes:
        """Witness transaction ID (hash with witness data)."""
        if self._whash is None:
            self._whash = sha256d(self.to_bytes(allow_witness=True))
        return self._whash

    def txid_hex(self) -> str:
        """Transaction ID as display hex (reversed byte order)."""
        return self.txid()[::-1].hex()

    # -- Properties ---------------------------------------------------------

    def has_witness(self) -> bool:
        return any(len(txin.script_witness) > 0 for txin in self.vin)

    def is_coinbase(self) -> bool:
        return len(self.vin) == 1 and self.vin[0].prevout.is_null()

    def get_value_out(self) -> int:
        """Sum of all output values."""
        return sum(txout.value for txout in self.vout)

    def __repr__(self) -> str:
        return f"CTransaction(txid={self.txid_hex()[:16]}..., vin={len(self.vin)}, vout={len(self.vout)})"
