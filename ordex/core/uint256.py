"""
256-bit unsigned integer type for block hashes, proof-of-work targets, etc.

Mirrors Bitcoin Core's arith_uint256 / uint256 types.  The internal
representation is a Python ``int`` (arbitrary precision), but all
serialization is 32-byte little-endian.
"""

from __future__ import annotations


class Uint256:
    """Immutable 256-bit unsigned integer."""

    __slots__ = ("_value",)

    MAX = (1 << 256) - 1

    def __init__(self, value: int = 0) -> None:
        if value < 0 or value > self.MAX:
            raise ValueError(f"Uint256 out of range: {value}")
        self._value = value

    # -- Constructors -------------------------------------------------------

    @classmethod
    def from_bytes_le(cls, data: bytes) -> "Uint256":
        """Create from 32-byte little-endian representation."""
        if len(data) != 32:
            raise ValueError(f"Expected 32 bytes, got {len(data)}")
        return cls(int.from_bytes(data, "little"))

    @classmethod
    def from_hex(cls, hex_str: str) -> "Uint256":
        """Create from a hex string (big-endian, like block hashes are displayed)."""
        hex_str = hex_str.strip()
        if hex_str.startswith("0x"):
            hex_str = hex_str[2:]
        hex_str = hex_str.zfill(64)
        return cls(int(hex_str, 16))

    @classmethod
    def from_compact(cls, compact: int) -> "Uint256":
        """Decode the nBits compact representation into a full 256-bit target.

        Format: the top byte is the number of bytes (exponent), and the lower
        3 bytes are the mantissa. Negative flag is the MSB of the mantissa.
        """
        size = (compact >> 24) & 0xFF
        negative = (compact >> 23) & 1
        mantissa = compact & 0x7FFFFF

        if size <= 3:
            mantissa >>= 8 * (3 - size)
            word = mantissa
        else:
            word = mantissa << (8 * (size - 3))

        if negative and word != 0:
            return cls(0)  # negative targets treated as zero

        word &= cls.MAX
        return cls(word)

    # -- Serialization ------------------------------------------------------

    def to_bytes_le(self) -> bytes:
        """Return the 32-byte little-endian representation."""
        return self._value.to_bytes(32, "little")

    def to_hex(self) -> str:
        """Return the big-endian hex string (like block hash display)."""
        return f"{self._value:064x}"

    def get_compact(self) -> int:
        """Encode as the nBits compact representation."""
        bn = self._value
        
        # Handle zero explicitly - compact representation of 0 is (0 << 24) | 0
        if bn == 0:
            return 0
        
        size = 0
        # Determine byte-length
        tmp = bn
        while tmp > 0:
            tmp >>= 8
            size += 1

        if size <= 3:
            compact = (bn & 0xFFFFFF) << (8 * (3 - size))
        else:
            compact = (bn >> (8 * (size - 3))) & 0xFFFFFF

        # Avoid setting the sign bit
        if compact & 0x800000:
            compact >>= 8
            size += 1

        return (size << 24) | compact

    # -- Bit operations (for OXG overflow fix) ------------------------------

    def bits(self) -> int:
        """Return the position of the highest set bit (1-indexed), or 0."""
        return self._value.bit_length()

    def __rshift__(self, n: int) -> "Uint256":
        return Uint256(self._value >> n)

    def __lshift__(self, n: int) -> "Uint256":
        return Uint256((self._value << n) & self.MAX)

    # -- Arithmetic ---------------------------------------------------------

    def __mul__(self, other: int) -> "Uint256":
        if isinstance(other, Uint256):
            other = other._value
        return Uint256((self._value * other) & self.MAX)

    def __rmul__(self, other: int) -> "Uint256":
        return self.__mul__(other)

    def __floordiv__(self, other: int) -> "Uint256":
        if isinstance(other, Uint256):
            other = other._value
        return Uint256(self._value // other)

    def __truediv__(self, other: int) -> "Uint256":
        return self.__floordiv__(other)

    def __add__(self, other: "Uint256") -> "Uint256":
        ov = other._value if isinstance(other, Uint256) else other
        return Uint256((self._value + ov) & self.MAX)

    def __sub__(self, other: "Uint256") -> "Uint256":
        """Subtract another value. Result wraps around (unsigned)."""
        ov = other._value if isinstance(other, Uint256) else other
        return Uint256((self._value - ov) & self.MAX)

    # -- Comparison ---------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Uint256):
            return self._value == other._value
        if isinstance(other, int):
            return self._value == other
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: "Uint256") -> bool:
        ov = other._value if isinstance(other, Uint256) else other
        return self._value < ov

    def __le__(self, other: "Uint256") -> bool:
        ov = other._value if isinstance(other, Uint256) else other
        return self._value <= ov

    def __gt__(self, other: "Uint256") -> bool:
        ov = other._value if isinstance(other, Uint256) else other
        return self._value > ov

    def __ge__(self, other: "Uint256") -> bool:
        ov = other._value if isinstance(other, Uint256) else other
        return self._value >= ov

    def __hash__(self) -> int:
        return hash(self._value)

    def __int__(self) -> int:
        return self._value

    def __bool__(self) -> bool:
        return self._value != 0

    def __repr__(self) -> str:
        return f"Uint256(0x{self.to_hex()})"

    def __str__(self) -> str:
        return self.to_hex()


# Convenience constant
UINT256_ZERO = Uint256(0)
