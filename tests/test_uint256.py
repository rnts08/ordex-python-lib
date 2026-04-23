"""
Tests for Uint256 256-bit integer.
"""

import pytest

from ordex.core.uint256 import Uint256


class TestUint256Constructors:
    """Tests for Uint256 construction."""

    def test_init_zero(self):
        u = Uint256(0)
        assert u._value == 0

    def test_init_negative_fails(self):
        with pytest.raises(ValueError, match="out of range"):
            Uint256(-1)

    def test_init_too_large_fails(self):
        with pytest.raises(ValueError, match="out of range"):
            Uint256(1 << 256)

    def test_from_bytes_le(self):
        data = bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000000")
        u = Uint256.from_bytes_le(data)
        assert u._value == 1

    def test_from_bytes_le_wrong_length(self):
        with pytest.raises(ValueError, match="Expected 32 bytes"):
            Uint256.from_bytes_le(b"\x00")

    def test_from_hex(self):
        u = Uint256.from_hex("0000000000000000000000000000000000000000000000000000000000000001")
        assert u._value == 1

    def test_from_hex_with_prefix(self):
        u = Uint256.from_hex("0x1")
        assert u._value == 1

    def test_from_compact_zero(self):
        u = Uint256.from_compact(0)
        assert u._value == 0

    def test_from_compact_normal(self):
        u = Uint256.from_compact(0x1d00ffff)
        assert u._value > 0


class TestUint256Serialization:
    """Tests for Uint256 serialization."""

    def test_to_bytes_le(self):
        u = Uint256(1)
        assert u.to_bytes_le() == bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000000")

    def test_to_hex(self):
        u = Uint256(1)
        assert u.to_hex() == "0000000000000000000000000000000000000000000000000000000000000001"

    def test_roundtrip_bytes(self):
        original = Uint256(0x1234567890abcdef)
        data = original.to_bytes_le()
        restored = Uint256.from_bytes_le(data)
        assert restored._value == original._value

    def test_roundtrip_hex(self):
        original = Uint256.from_hex("abcdef")
        hex_str = original.to_hex()
        restored = Uint256.from_hex(hex_str)
        assert restored._value == original._value


class TestUint256Arithmetic:
    """Tests for Uint256 arithmetic."""

    def test_add(self):
        a = Uint256(1)
        b = Uint256(2)
        c = a + b
        assert c._value == 3

    def test_sub(self):
        a = Uint256(5)
        b = Uint256(3)
        c = a - b
        assert c._value == 2

    def test_mul(self):
        a = Uint256(3)
        b = a * 4
        assert b._value == 12

    def test_floordiv(self):
        a = Uint256(10)
        b = a // 3
        assert b._value == 3


class TestUint256BitOperations:
    """Tests for Uint256 bit operations."""

    def test_rshift(self):
        a = Uint256(8)
        b = a >> 1
        assert b._value == 4

    def test_lshift(self):
        a = Uint256(1)
        b = a << 3
        assert b._value == 8

    def test_bits(self):
        a = Uint256(0xFF)
        assert a.bits() == 8


class TestUint256Comparison:
    """Tests for Uint256 comparison."""

    def test_equality(self):
        a = Uint256(42)
        b = Uint256(42)
        assert a == b

    def test_inequality(self):
        a = Uint256(1)
        b = Uint256(2)
        assert a != b

    def test_less_than(self):
        a = Uint256(1)
        b = Uint256(2)
        assert a < b

    def test_greater_than(self):
        a = Uint256(2)
        b = Uint256(1)
        assert a > b


class TestUint256Compact:
    """Tests for get_compact/from_compact roundtrip."""

    def test_compact_zero(self):
        u = Uint256(0)
        compact = u.get_compact()
        assert compact == 0

    def test_compact_roundtrip_basic(self):
        u = Uint256(1)
        compact = u.get_compact()
        restored = Uint256.from_compact(compact)
        assert restored._value == 1