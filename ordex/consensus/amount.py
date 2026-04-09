"""
Amount constants and validation for OrdexCoin and OrdexGold.
"""

from __future__ import annotations

# 1 coin = 100,000,000 satoshis (same as Bitcoin)
COIN = 100_000_000

# Maximum valid amounts per chain (consensus-critical)
MAX_MONEY_OXC = 8_450_000 * COIN
MAX_MONEY_OXG = 1_001_000 * COIN


def money_range(value: int, *, max_money: int = MAX_MONEY_OXC) -> bool:
    """Check if a monetary value is within the valid range [0, MAX_MONEY]."""
    return 0 <= value <= max_money


def format_money(value: int) -> str:
    """Format a satoshi value as a human-readable coin amount."""
    negative = value < 0
    value = abs(value)
    whole = value // COIN
    frac = value % COIN
    s = f"{whole}.{frac:08d}"
    # Strip trailing zeros but keep at least 2 decimal places
    s = s.rstrip("0")
    if "." in s:
        integer, decimal = s.split(".")
        decimal = decimal.ljust(2, "0")
        s = f"{integer}.{decimal}"
    if negative:
        s = "-" + s
    return s


def parse_money(s: str) -> int:
    """Parse a coin amount string into satoshis."""
    s = s.strip()
    negative = s.startswith("-")
    if negative:
        s = s[1:]
    if "." in s:
        whole, frac = s.split(".", 1)
        frac = frac.ljust(8, "0")[:8]
    else:
        whole = s
        frac = "00000000"
    value = int(whole) * COIN + int(frac)
    return -value if negative else value
