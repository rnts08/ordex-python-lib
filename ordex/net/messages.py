"""
P2P message serialization / deserialization.

Implements the core Bitcoin P2P messages needed for handshake,
ping/pong, block/transaction exchange, and header syncing.
"""

from __future__ import annotations

import random
import time
from io import BytesIO
from typing import BinaryIO, List, Optional

from ordex.core.serialize import (
    read_int32, write_int32,
    read_uint32, write_uint32,
    read_int64, write_int64,
    read_uint64, write_uint64,
    read_compact_size, write_compact_size,
    read_string, write_string,
    read_hash256, write_hash256,
    read_bytes,
)
from ordex.net.protocol import CInv, ServiceFlags


class MsgVersion:
    """``version`` message — initiates the P2P handshake."""

    __slots__ = (
        "version", "services", "timestamp",
        "addr_recv_services", "addr_recv_ip", "addr_recv_port",
        "addr_from_services", "addr_from_ip", "addr_from_port",
        "nonce", "user_agent", "start_height", "relay",
    )

    def __init__(
        self,
        version: int = 70016,
        services: int = ServiceFlags.NODE_NETWORK | ServiceFlags.NODE_WITNESS,
        timestamp: Optional[int] = None,
        user_agent: str = "/ordex-python:0.1.0/",
        start_height: int = 0,
        relay: bool = True,
    ) -> None:
        self.version = version
        self.services = services
        self.timestamp = timestamp or int(time.time())
        self.addr_recv_services = ServiceFlags.NODE_NETWORK
        self.addr_recv_ip = b"\x00" * 16
        self.addr_recv_port = 0
        self.addr_from_services = services
        self.addr_from_ip = b"\x00" * 16
        self.addr_from_port = 0
        self.nonce = random.getrandbits(64)
        self.user_agent = user_agent
        self.start_height = start_height
        self.relay = relay

    def serialize(self, f: BinaryIO) -> None:
        write_int32(f, self.version)
        write_uint64(f, self.services)
        write_int64(f, self.timestamp)

        # addr_recv
        write_uint64(f, self.addr_recv_services)
        f.write(self.addr_recv_ip)
        f.write(self.addr_recv_port.to_bytes(2, "big"))

        # addr_from
        write_uint64(f, self.addr_from_services)
        f.write(self.addr_from_ip)
        f.write(self.addr_from_port.to_bytes(2, "big"))

        write_uint64(f, self.nonce)
        ua_bytes = self.user_agent.encode("utf-8")
        write_string(f, ua_bytes)
        write_int32(f, self.start_height)
        f.write(b"\x01" if self.relay else b"\x00")

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgVersion":
        msg = cls.__new__(cls)
        msg.version = read_int32(f)
        msg.services = read_uint64(f)
        msg.timestamp = read_int64(f)

        msg.addr_recv_services = read_uint64(f)
        msg.addr_recv_ip = read_bytes(f, 16)
        msg.addr_recv_port = int.from_bytes(read_bytes(f, 2), "big")

        msg.addr_from_services = read_uint64(f)
        msg.addr_from_ip = read_bytes(f, 16)
        msg.addr_from_port = int.from_bytes(read_bytes(f, 2), "big")

        msg.nonce = read_uint64(f)
        msg.user_agent = read_string(f).decode("utf-8", errors="replace")
        msg.start_height = read_int32(f)

        # relay flag is optional (BIP37)
        remaining = f.read(1)
        msg.relay = remaining == b"\x01" if remaining else True
        return msg

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgPing:
    """``ping`` message."""

    __slots__ = ("nonce",)

    def __init__(self, nonce: Optional[int] = None) -> None:
        self.nonce = nonce if nonce is not None else random.getrandbits(64)

    def serialize(self, f: BinaryIO) -> None:
        write_uint64(f, self.nonce)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgPing":
        return cls(read_uint64(f))

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgPong:
    """``pong`` message — response to ``ping``."""

    __slots__ = ("nonce",)

    def __init__(self, nonce: int = 0) -> None:
        self.nonce = nonce

    def serialize(self, f: BinaryIO) -> None:
        write_uint64(f, self.nonce)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgPong":
        return cls(read_uint64(f))

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgInv:
    """``inv`` message — announce inventory."""

    __slots__ = ("inventory",)

    def __init__(self, inventory: Optional[List[CInv]] = None) -> None:
        self.inventory = inventory or []

    def serialize(self, f: BinaryIO) -> None:
        write_compact_size(f, len(self.inventory))
        for inv in self.inventory:
            inv.serialize(f)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgInv":
        count = read_compact_size(f)
        inventory = [CInv.deserialize(f) for _ in range(count)]
        return cls(inventory)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgGetData:
    """``getdata`` message — request objects from a peer."""

    __slots__ = ("inventory",)

    def __init__(self, inventory: Optional[List[CInv]] = None) -> None:
        self.inventory = inventory or []

    def serialize(self, f: BinaryIO) -> None:
        write_compact_size(f, len(self.inventory))
        for inv in self.inventory:
            inv.serialize(f)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgGetData":
        count = read_compact_size(f)
        inventory = [CInv.deserialize(f) for _ in range(count)]
        return cls(inventory)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgGetHeaders:
    """``getheaders`` message — request block headers."""

    __slots__ = ("version", "block_locator_hashes", "hash_stop")

    def __init__(
        self,
        version: int = 70016,
        block_locator_hashes: Optional[List[bytes]] = None,
        hash_stop: bytes = b"\x00" * 32,
    ) -> None:
        self.version = version
        self.block_locator_hashes = block_locator_hashes or []
        self.hash_stop = hash_stop

    def serialize(self, f: BinaryIO) -> None:
        write_uint32(f, self.version)
        write_compact_size(f, len(self.block_locator_hashes))
        for h in self.block_locator_hashes:
            write_hash256(f, h)
        write_hash256(f, self.hash_stop)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgGetHeaders":
        msg = cls.__new__(cls)
        msg.version = read_uint32(f)
        count = read_compact_size(f)
        msg.block_locator_hashes = [read_hash256(f) for _ in range(count)]
        msg.hash_stop = read_hash256(f)
        return msg

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgHeaders:
    """``headers`` message — response to getheaders, contains block headers."""

    __slots__ = ("headers",)

    def __init__(self, headers: Optional[List["CBlockHeader"]] = None) -> None:
        self.headers = headers or []

    def serialize(self, f: BinaryIO) -> None:
        write_compact_size(f, len(self.headers))
        for header in self.headers:
            header.serialize(f)
            f.write(b"\x00")  # txn_count = 0 (no transactions in header message)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgHeaders":
        count = read_compact_size(f)
        from ordex.primitives.block import CBlockHeader
        headers = []
        for _ in range(count):
            headers.append(CBlockHeader.deserialize(f))
            txn_count = read_compact_size(f)
        return cls(headers)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgMerkleBlock:
    """``merkleblock`` message — filtered block with merkle proofs for SPV.

    Contains a block header plus a partial merkle tree showing which
    transactions match the bloom filter.
    """

    __slots__ = ("header", "transaction_count", "hashes", "flags")

    def __init__(
        self,
        header: "CBlockHeader" = None,
        transaction_count: int = 0,
        hashes: Optional[List[bytes]] = None,
        flags: bytes = b"",
    ) -> None:
        from ordex.primitives.block import CBlockHeader
        self.header = header or CBlockHeader()
        self.transaction_count = transaction_count
        self.hashes = hashes or []
        self.flags = flags

    def serialize(self, f: BinaryIO) -> None:
        self.header.serialize(f)
        write_uint32(f, self.transaction_count)
        write_compact_size(f, len(self.hashes))
        for h in self.hashes:
            write_hash256(f, h)
        write_compact_size(f, len(self.flags))
        f.write(self.flags)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgMerkleBlock":
        from ordex.primitives.block import CBlockHeader
        header = CBlockHeader.deserialize(f)
        tx_count = read_uint32(f)
        num_hashes = read_compact_size(f)
        hashes = [read_hash256(f) for _ in range(num_hashes)]
        num_flags = read_compact_size(f)
        flags = f.read(num_flags)
        return cls(header, tx_count, hashes, flags)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class CAddress:
    """Network address (16 bytes IP + 2 bytes port + services)."""

    __slots__ = ("services", "ip", "port", "timestamp")

    def __init__(
        self,
        services: int = 0,
        ip: bytes = b"\x00" * 16,
        port: int = 0,
        timestamp: Optional[int] = None,
    ) -> None:
        self.services = services
        self.ip = ip
        self.port = port
        self.timestamp = timestamp

    def serialize(self, f: BinaryIO) -> None:
        if self.timestamp is not None and self.timestamp > 0:
            write_uint32(f, self.timestamp)
        write_uint64(f, self.services)
        f.write(self.ip)
        f.write(self.port.to_bytes(2, "big"))

    @classmethod
    def deserialize(cls, f: BinaryIO, has_timestamp: bool = True) -> "CAddress":
        if has_timestamp:
            timestamp = read_uint32(f)
        else:
            timestamp = None
        services = read_uint64(f)
        ip = read_bytes(f, 16)
        port = int.from_bytes(read_bytes(f, 2), "big")
        return cls(services, ip, port, timestamp)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgAddr:
    """``addr`` message — network addresses."""

    __slots__ = ("addresses",)

    def __init__(self, addresses: Optional[List[CAddress]] = None) -> None:
        self.addresses = addresses or []

    def serialize(self, f: BinaryIO) -> None:
        write_compact_size(f, len(self.addresses))
        for addr in self.addresses:
            addr.serialize(f)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgAddr":
        count = read_compact_size(f)
        addresses = [CAddress.deserialize(f) for _ in range(count)]
        return cls(addresses)

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()


class MsgMempool:
    """``mempool`` message — request transaction inventory."""

    def __init__(self) -> None:
        pass

    def serialize(self, f: BinaryIO) -> None:
        pass

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "MsgMempool":
        return cls()

    def to_bytes(self) -> bytes:
        return b""
