"""
Tests for amount constants and validation.
"""

import pytest

from ordex.consensus.amount import COIN, MAX_MONEY_OXC, MAX_MONEY_OXG, money_range, format_money, parse_money


class TestConstants:
    """Tests for amount constants."""

    def test_coin_value(self):
        assert COIN == 100_000_000

    def test_max_money_oxc(self):
        assert MAX_MONEY_OXC == 8_450_000 * COIN

    def test_max_money_oxg(self):
        assert MAX_MONEY_OXG == 1_001_000 * COIN


class TestMoneyRange:
    """Tests for money_range validation."""

    def test_zero_valid(self):
        assert money_range(0) is True

    def test_within_limit_valid(self):
        valid = MAX_MONEY_OXC // 2
        assert money_range(valid) is True

    def test_at_limit_valid(self):
        assert money_range(MAX_MONEY_OXC) is True

    def test_above_limit_invalid(self):
        invalid = MAX_MONEY_OXC + 1
        assert money_range(invalid) is False

    def test_negative_invalid(self):
        assert money_range(-1) is False

    def test_custom_max(self):
        custom_max = 1000 * COIN
        assert money_range(500 * COIN, max_money=custom_max) is True


class TestFormatMoney:
    """Tests for format_money."""

    def test_format_whole_coins(self):
        result = format_money(1 * COIN)
        assert "1" in result

    def test_format_satoshis(self):
        result = format_money(1)
        assert "00000001" in result

    def test_format_fraction(self):
        result = format_money(123456789)
        assert "23456789" in result or "123456789" in result

    def test_format_negative(self):
        result = format_money(-COIN)
        assert result.startswith("-")


class TestParseMoney:
    """Tests for parse_money."""

    def test_parse_whole_coins(self):
        result = parse_money("1")
        assert result == COIN

    def test_parse_fraction(self):
        result = parse_money("0.5")
        assert result == 50_000_000

    def test_parse_satoshis(self):
        result = parse_money("0.00000001")
        assert result == 1

    def test_parse_negative(self):
        result = parse_money("-1")
        assert result == -COIN

    def test_parse_with_leading_zeros(self):
        result = parse_money("001")
        assert result == COIN


class TestRoundtrip:
    """Tests for format/parse roundtrip."""

    def test_roundtrip_coin(self):
        original = "1.5"
        parsed = parse_money(original)
        formatted = format_money(parsed)
        assert float(formatted) == float(original)