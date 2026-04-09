"""
Base58Check and Bech32/Bech32m encoding/decoding.

Used for generating human-readable OrdexCoin and OrdexGold addresses.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ordex.core.hash import sha256d

# ---------------------------------------------------------------------------
# Base58 alphabet
# ---------------------------------------------------------------------------

BASE58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_BASE58_MAP = {c: i for i, c in enumerate(BASE58_ALPHABET)}


def b58encode(data: bytes) -> str:
    """Encode bytes to a Base58 string."""
    n = int.from_bytes(data, "big")
    result = []
    while n > 0:
        n, r = divmod(n, 58)
        result.append(BASE58_ALPHABET[r:r + 1])
    # Preserve leading zero bytes
    for byte in data:
        if byte == 0:
            result.append(b"1")
        else:
            break
    return b"".join(reversed(result)).decode("ascii")


def b58decode(s: str) -> bytes:
    """Decode a Base58 string to bytes."""
    n = 0
    for ch in s.encode("ascii"):
        n = n * 58 + _BASE58_MAP[ch]
    # Count leading '1's → leading zero bytes
    pad_size = 0
    for ch in s:
        if ch == "1":
            pad_size += 1
        else:
            break
    # Determine byte length
    byte_length = (n.bit_length() + 7) // 8
    result = n.to_bytes(max(byte_length, 1), "big")
    return b"\x00" * pad_size + result


def b58check_encode(version: bytes, payload: bytes) -> str:
    """Encode with Base58Check (version + payload + 4-byte checksum)."""
    data = version + payload
    checksum = sha256d(data)[:4]
    return b58encode(data + checksum)


def b58check_decode(s: str) -> Tuple[bytes, bytes]:
    """Decode Base58Check, returning (version_byte, payload).

    Raises ValueError on checksum mismatch.
    """
    data = b58decode(s)
    payload, checksum = data[:-4], data[-4:]
    if sha256d(payload)[:4] != checksum:
        raise ValueError("Base58Check checksum mismatch")
    return payload[:1], payload[1:]


# ---------------------------------------------------------------------------
# Bech32 / Bech32m (BIP173 / BIP350)
# ---------------------------------------------------------------------------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_CHARSET_MAP = {c: i for i, c in enumerate(_BECH32_CHARSET)}


def _bech32_polymod(values: list[int]) -> int:
    """Internal Bech32 checksum polymod function."""
    GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]
    chk = 1
    for v in values:
        b = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            chk ^= GEN[i] if ((b >> i) & 1) else 0
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    """Expand the HRP for checksum computation."""
    return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]


def _bech32_create_checksum(hrp: str, data: list[int], spec: int) -> list[int]:
    """Create a Bech32/Bech32m checksum."""
    # spec: 1 = bech32, 0x2bc830a3 = bech32m
    const = 1 if spec == 1 else 0x2BC830A3
    values = _bech32_hrp_expand(hrp) + data
    polymod = _bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ const
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _bech32_verify_checksum(hrp: str, data: list[int]) -> Optional[int]:
    """Verify checksum, returning the Bech32 spec version or None."""
    const = _bech32_polymod(_bech32_hrp_expand(hrp) + data)
    if const == 1:
        return 1  # bech32
    if const == 0x2BC830A3:
        return 2  # bech32m
    return None


def _convertbits(data: bytes | list[int], frombits: int, tobits: int, pad: bool = True) -> list[int]:
    """General power-of-2 base conversion."""
    acc = 0
    bits = 0
    ret = []
    maxv = (1 << tobits) - 1
    for value in data:
        if value < 0 or (value >> frombits):
            raise ValueError(f"Invalid value for convertbits: {value}")
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            ret.append((acc >> bits) & maxv)
    if pad:
        if bits:
            ret.append((acc << (tobits - bits)) & maxv)
    elif bits >= frombits or ((acc << (tobits - bits)) & maxv):
        raise ValueError("Invalid padding in convertbits")
    return ret


def bech32_encode(hrp: str, witver: int, witprog: bytes) -> str:
    """Encode a witness program as a Bech32/Bech32m address.

    witver 0 uses Bech32 (BIP173), witver 1+ uses Bech32m (BIP350).
    """
    spec = 1 if witver == 0 else 2
    data = [witver] + _convertbits(witprog, 8, 5)
    checksum = _bech32_create_checksum(hrp, data, spec)
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in data + checksum)


def bech32_decode(bech: str) -> Tuple[str, int, bytes]:
    """Decode a Bech32/Bech32m address.

    Returns (hrp, witness_version, witness_program).
    Raises ValueError on invalid encoding.
    """
    bech_lower = bech.lower()
    pos = bech_lower.rfind("1")
    if pos < 1 or pos + 7 > len(bech_lower):
        raise ValueError("Invalid bech32 string")
    if any(ord(x) < 33 or ord(x) > 126 for x in bech_lower):
        raise ValueError("Invalid characters in bech32 string")

    hrp = bech_lower[:pos]
    data_part = bech_lower[pos + 1:]

    try:
        data = [_BECH32_CHARSET_MAP[c] for c in data_part]
    except KeyError:
        raise ValueError("Invalid character in bech32 data")

    spec = _bech32_verify_checksum(hrp, data)
    if spec is None:
        raise ValueError("Bech32 checksum verification failed")

    decoded = data[:-6]  # strip checksum
    if len(decoded) < 1:
        raise ValueError("Empty bech32 data")

    witver = decoded[0]
    witprog = bytes(_convertbits(decoded[1:], 5, 8, pad=False))

    if witver == 0 and spec != 1:
        raise ValueError("Witness v0 must use Bech32 encoding")
    if witver != 0 and spec != 2:
        raise ValueError("Witness v1+ must use Bech32m encoding")

    return hrp, witver, witprog
