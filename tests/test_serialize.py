"""
Tests for core serialization, hashing, and uint256 types.
"""

import struct
from io import BytesIO

import pytest

from ordex.core.serialize import (
    read_compact_size, write_compact_size,
    read_int32, write_int32,
    read_uint32, write_uint32,
    read_string, write_string,
    read_vector, write_vector,
)
from ordex.core.uint256 import Uint256
from ordex.core.hash import sha256d, hash160, scrypt_hash


class TestCompactSize:
    """CompactSize (varint) encoding/decoding."""

    @pytest.mark.parametrize("value,expected_bytes", [
        (0, b"\x00"),
        (1, b"\x01"),
        (252, b"\xfc"),
        (253, b"\xfd\xfd\x00"),
        (0xFFFF, b"\xfd\xff\xff"),
        (0x10000, b"\xfe\x00\x00\x01\x00"),
        (0xFFFFFFFF, b"\xfe\xff\xff\xff\xff"),
        (0x100000000, b"\xff\x00\x00\x00\x00\x01\x00\x00\x00"),
    ])
    def test_roundtrip(self, value, expected_bytes):
        buf = BytesIO()
        write_compact_size(buf, value)
        assert buf.getvalue() == expected_bytes

        buf.seek(0)
        assert read_compact_size(buf) == value


class TestIntegerIO:
    """Fixed-width little-endian integer I/O."""

    def test_int32_roundtrip(self):
        for val in [0, 1, -1, 2147483647, -2147483648]:
            buf = BytesIO()
            write_int32(buf, val)
            buf.seek(0)
            assert read_int32(buf) == val

    def test_uint32_roundtrip(self):
        for val in [0, 1, 0xFFFFFFFF, 0xDEADBEEF]:
            buf = BytesIO()
            write_uint32(buf, val)
            buf.seek(0)
            assert read_uint32(buf) == val


class TestStringIO:
    """Length-prefixed string I/O."""

    def test_roundtrip(self):
        data = b"Memento Mori"
        buf = BytesIO()
        write_string(buf, data)
        buf.seek(0)
        assert read_string(buf) == data

    def test_empty(self):
        buf = BytesIO()
        write_string(buf, b"")
        buf.seek(0)
        assert read_string(buf) == b""


class TestUint256:
    """256-bit unsigned integer."""

    def test_from_hex(self):
        u = Uint256.from_hex("0000000000000000000000000000000000000000000000000000000000000001")
        assert int(u) == 1

    def test_from_compact(self):
        # 0x1d00ffff → standard Bitcoin genesis target
        target = Uint256.from_compact(0x1d00ffff)
        assert target > Uint256(0)
        # Should be 0x00000000FFFF00000000...
        hex_str = target.to_hex()
        assert hex_str.startswith("00000000ffff")

    def test_get_compact_roundtrip(self):
        for compact in [0x1e0ffff0, 0x207fffff, 0x1d00ffff]:
            val = Uint256.from_compact(compact)
            # Roundtrip may not be exact for all compact values due to precision
            rt = val.get_compact()
            val2 = Uint256.from_compact(rt)
            assert val == val2

    def test_get_compact_zero(self):
        """Test that zero produces valid compact encoding that roundtrips."""
        u = Uint256(0)
        compact = u.get_compact()
        assert compact == 0
        # Verify roundtrip
        u2 = Uint256.from_compact(compact)
        assert u == u2

    def test_from_compact_zero(self):
        """Test that compact 0 decodes to zero target."""
        u = Uint256.from_compact(0)
        assert u == Uint256(0)
        assert u._value == 0

    def test_bytes_roundtrip(self):
        original = Uint256(0xDEADBEEF)
        data = original.to_bytes_le()
        restored = Uint256.from_bytes_le(data)
        assert original == restored

    def test_comparison(self):
        a = Uint256(100)
        b = Uint256(200)
        assert a < b
        assert b > a
        assert a != b
        assert a == Uint256(100)


class TestHash:
    """Cryptographic hash functions."""

    def test_sha256d_empty(self):
        # SHA-256d of empty string is known
        result = sha256d(b"")
        expected = bytes.fromhex(
            "5df6e0e2761359d30a8275058e299fcc0381534545f55cf43e41983f5d4c9456"
        )
        assert result == expected

    def test_hash160(self):
        # hash160 of a known value
        result = hash160(b"\x00")
        assert len(result) == 20

    def test_scrypt_produces_32_bytes(self):
        """Scrypt should produce a 32-byte hash from an 80-byte header."""
        fake_header = b"\x00" * 80
        result = scrypt_hash(fake_header)
        assert len(result) == 32
