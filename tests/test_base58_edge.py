"""
Tests for base58 encoding edge cases.
"""

import pytest

from ordex.core.base58 import b58encode, b58decode


class TestBase58LeadingZeros:
    """Tests for base58 leading zeros handling."""

    def test_encode_leading_zero(self):
        data = b"\x00\x00test"
        result = b58encode(data)
        assert result.startswith("11")

    def test_roundtrip_leading_zeros(self):
        original = b"\x00\x00test"[2:]  # Skip leading zeros
        encoded = b58encode(original)
        decoded = b58decode(encoded)
        assert decoded == original

    def test_encode_all_zeros(self):
        data = b"\x00\x00\x00"
        result = b58encode(data)
        assert result == "111"

    def test_single_leading_zero(self):
        data = b"\x00test"
        result = b58encode(data)
        assert result.startswith("1")