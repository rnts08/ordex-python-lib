"""
P2P protocol definitions: message header, inventory vectors, service flags.

Matches the on-wire format used by ordexcoind / ordexgoldd.
"""

from __future__ import annotations

import enum
import struct
from io import BytesIO
from typing import BinaryIO, List

from ordex.core.hash import sha256d
from ordex.core.serialize import (
    read_bytes, write_bytes,
    read_uint32, write_uint32,
    read_uint64, write_uint64,
    read_compact_size, write_compact_size,
    read_hash256, write_hash256,
)


# ---------------------------------------------------------------------------
# Service flags
# ---------------------------------------------------------------------------

class ServiceFlags(enum.IntFlag):
    NODE_NONE = 0
    NODE_NETWORK = 1 << 0
    NODE_BLOOM = 1 << 2
    NODE_WITNESS = 1 << 3
    NODE_COMPACT_FILTERS = 1 << 6
    NODE_NETWORK_LIMITED = 1 << 10


# ---------------------------------------------------------------------------
# Inventory message types
# ---------------------------------------------------------------------------

class InvType(enum.IntEnum):
    UNDEFINED = 0
    MSG_TX = 1
    MSG_BLOCK = 2
    MSG_FILTERED_BLOCK = 3
    MSG_CMPCT_BLOCK = 4
    MSG_WTX = 5
    MSG_WITNESS_BLOCK = MSG_BLOCK | (1 << 30)
    MSG_WITNESS_TX = MSG_TX | (1 << 30)


# ---------------------------------------------------------------------------
# Message command strings
# ---------------------------------------------------------------------------

class NetMsgType:
    VERSION = "version"
    VERACK = "verack"
    ADDR = "addr"
    ADDRV2 = "addrv2"
    SENDADDRV2 = "sendaddrv2"
    INV = "inv"
    GETDATA = "getdata"
    MERKLEBLOCK = "merkleblock"
    GETBLOCKS = "getblocks"
    GETHEADERS = "getheaders"
    TX = "tx"
    HEADERS = "headers"
    BLOCK = "block"
    GETADDR = "getaddr"
    MEMPOOL = "mempool"
    PING = "ping"
    PONG = "pong"
    NOTFOUND = "notfound"
    FILTERLOAD = "filterload"
    FILTERADD = "filteradd"
    FILTERCLEAR = "filterclear"
    SENDHEADERS = "sendheaders"
    FEEFILTER = "feefilter"
    SENDCMPCT = "sendcmpct"
    CMPCTBLOCK = "cmpctblock"
    GETBLOCKTXN = "getblocktxn"
    BLOCKTXN = "blocktxn"
    WTXIDRELAY = "wtxidrelay"


# ---------------------------------------------------------------------------
# CMessageHeader — 24-byte P2P message header
# ---------------------------------------------------------------------------

class CMessageHeader:
    """P2P message header (24 bytes total).

    Layout:
        [4] message start (magic bytes)
        [12] command (null-padded ASCII)
        [4] payload size (uint32 LE)
        [4] checksum (first 4 bytes of SHA-256d of payload)
    """

    MESSAGE_START_SIZE = 4
    COMMAND_SIZE = 12
    CHECKSUM_SIZE = 4
    HEADER_SIZE = MESSAGE_START_SIZE + COMMAND_SIZE + 4 + CHECKSUM_SIZE  # 24

    __slots__ = ("message_start", "command", "payload_size", "checksum")

    def __init__(
        self,
        message_start: bytes = b"\x00" * 4,
        command: str = "",
        payload_size: int = 0,
        checksum: bytes = b"\x00" * 4,
    ) -> None:
        self.message_start = message_start
        self.command = command
        self.payload_size = payload_size
        self.checksum = checksum

    @classmethod
    def from_payload(cls, message_start: bytes, command: str, payload: bytes) -> "CMessageHeader":
        """Create a header for a given command and payload."""
        checksum = sha256d(payload)[:4]
        return cls(message_start, command, len(payload), checksum)

    def serialize(self, f: BinaryIO) -> None:
        f.write(self.message_start)
        cmd_bytes = self.command.encode("ascii")[:self.COMMAND_SIZE]
        f.write(cmd_bytes.ljust(self.COMMAND_SIZE, b"\x00"))
        write_uint32(f, self.payload_size)
        f.write(self.checksum)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "CMessageHeader":
        message_start = read_bytes(f, cls.MESSAGE_START_SIZE)
        cmd_raw = read_bytes(f, cls.COMMAND_SIZE)
        command = cmd_raw.rstrip(b"\x00").decode("ascii")
        payload_size = read_uint32(f)
        checksum = read_bytes(f, cls.CHECKSUM_SIZE)
        return cls(message_start, command, payload_size, checksum)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()

    def verify_checksum(self, payload: bytes) -> bool:
        """Verify the checksum against the actual payload."""
        return sha256d(payload)[:4] == self.checksum

    def __repr__(self) -> str:
        return (
            f"CMessageHeader(cmd={self.command!r}, "
            f"size={self.payload_size}, "
            f"magic={self.message_start.hex()})"
        )


# ---------------------------------------------------------------------------
# CInv — inventory vector
# ---------------------------------------------------------------------------

class CInv:
    """Inventory vector: type + hash."""

    __slots__ = ("type", "hash")

    def __init__(self, inv_type: int = 0, hash: bytes = b"\x00" * 32) -> None:
        self.type = inv_type
        self.hash = hash

    def serialize(self, f: BinaryIO) -> None:
        write_uint32(f, self.type)
        write_hash256(f, self.hash)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "CInv":
        inv_type = read_uint32(f)
        hash = read_hash256(f)
        return cls(inv_type, hash)

    def is_tx(self) -> bool:
        return (self.type & 0x3FFFFFFF) == InvType.MSG_TX

    def is_block(self) -> bool:
        return (self.type & 0x3FFFFFFF) == InvType.MSG_BLOCK

    def __repr__(self) -> str:
        return f"CInv(type={self.type}, hash={self.hash[:4].hex()}...)"
