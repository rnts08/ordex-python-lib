"""
Binary serialization primitives matching the Bitcoin/Ordex wire format.

Provides CompactSize (varint) encoding, little-endian integer I/O,
and vector/string serialization helpers.
"""

from __future__ import annotations

import struct
from io import BytesIO
from typing import BinaryIO, Callable, List, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# CompactSize (varint) encoding — Bitcoin's variable-length integer
# ---------------------------------------------------------------------------

def read_compact_size(f: BinaryIO) -> int:
    """Read a CompactSize-encoded unsigned integer from a stream."""
    first = f.read(1)
    if len(first) < 1:
        raise EOFError("Unexpected end of stream reading compact size")
    n = first[0]
    if n < 253:
        return n
    if n == 253:
        return struct.unpack("<H", _read_exactly(f, 2))[0]
    if n == 254:
        return struct.unpack("<I", _read_exactly(f, 4))[0]
    return struct.unpack("<Q", _read_exactly(f, 8))[0]


def write_compact_size(f: BinaryIO, n: int) -> None:
    """Write a CompactSize-encoded unsigned integer to a stream."""
    if n < 0:
        raise ValueError(f"CompactSize cannot be negative: {n}")
    if n < 253:
        f.write(struct.pack("B", n))
    elif n <= 0xFFFF:
        f.write(b"\xfd" + struct.pack("<H", n))
    elif n <= 0xFFFFFFFF:
        f.write(b"\xfe" + struct.pack("<I", n))
    else:
        f.write(b"\xff" + struct.pack("<Q", n))


# ---------------------------------------------------------------------------
# Fixed-width little-endian integer I/O
# ---------------------------------------------------------------------------

def read_uint8(f: BinaryIO) -> int:
    return struct.unpack("B", _read_exactly(f, 1))[0]

def write_uint8(f: BinaryIO, val: int) -> None:
    f.write(struct.pack("B", val))

def read_int32(f: BinaryIO) -> int:
    return struct.unpack("<i", _read_exactly(f, 4))[0]

def write_int32(f: BinaryIO, val: int) -> None:
    f.write(struct.pack("<i", val))

def read_uint32(f: BinaryIO) -> int:
    return struct.unpack("<I", _read_exactly(f, 4))[0]

def write_uint32(f: BinaryIO, val: int) -> None:
    f.write(struct.pack("<I", val))

def read_int64(f: BinaryIO) -> int:
    return struct.unpack("<q", _read_exactly(f, 8))[0]

def write_int64(f: BinaryIO, val: int) -> None:
    f.write(struct.pack("<q", val))

def read_uint64(f: BinaryIO) -> int:
    return struct.unpack("<Q", _read_exactly(f, 8))[0]

def write_uint64(f: BinaryIO, val: int) -> None:
    f.write(struct.pack("<Q", val))


# ---------------------------------------------------------------------------
# Raw bytes
# ---------------------------------------------------------------------------

def read_bytes(f: BinaryIO, n: int) -> bytes:
    """Read exactly *n* bytes from *f*."""
    return _read_exactly(f, n)

def write_bytes(f: BinaryIO, data: bytes) -> None:
    f.write(data)


# ---------------------------------------------------------------------------
# Length-prefixed byte strings
# ---------------------------------------------------------------------------

def read_string(f: BinaryIO) -> bytes:
    """Read a CompactSize-length-prefixed byte string."""
    length = read_compact_size(f)
    return _read_exactly(f, length)

def write_string(f: BinaryIO, data: bytes) -> None:
    """Write a CompactSize-length-prefixed byte string."""
    write_compact_size(f, len(data))
    f.write(data)


# ---------------------------------------------------------------------------
# Vector serialization
# ---------------------------------------------------------------------------

def read_vector(f: BinaryIO, deserialize_fn: Callable[[BinaryIO], T]) -> List[T]:
    """Read a vector: CompactSize count followed by *count* elements."""
    count = read_compact_size(f)
    return [deserialize_fn(f) for _ in range(count)]

def write_vector(f: BinaryIO, items: List[T], serialize_fn: Callable[[BinaryIO, T], None]) -> None:
    """Write a vector: CompactSize count followed by serialized elements."""
    write_compact_size(f, len(items))
    for item in items:
        serialize_fn(f, item)


# ---------------------------------------------------------------------------
# Hash (32-byte value) serialization — stored in internal byte order
# ---------------------------------------------------------------------------

def read_hash256(f: BinaryIO) -> bytes:
    """Read a 256-bit hash (32 bytes, internal byte order)."""
    return _read_exactly(f, 32)

def write_hash256(f: BinaryIO, h: bytes) -> None:
    """Write a 256-bit hash (32 bytes)."""
    assert len(h) == 32, f"Hash must be 32 bytes, got {len(h)}"
    f.write(h)


# ---------------------------------------------------------------------------
# Convenience: serialize to / deserialize from bytes
# ---------------------------------------------------------------------------

def to_bytes(write_fn: Callable[[BinaryIO], None]) -> bytes:
    """Serialize an object to bytes via a write callback."""
    buf = BytesIO()
    write_fn(buf)
    return buf.getvalue()

def from_bytes(data: bytes, read_fn: Callable[[BinaryIO], T]) -> T:
    """Deserialize an object from bytes via a read callback."""
    return read_fn(BytesIO(data))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_exactly(f: BinaryIO, n: int) -> bytes:
    """Read exactly *n* bytes, raising EOFError on short read."""
    data = f.read(n)
    if len(data) < n:
        raise EOFError(f"Expected {n} bytes, got {len(data)}")
    return data
