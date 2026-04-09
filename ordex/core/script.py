"""
Bitcoin Script primitives.

Provides opcode constants, the CScript byte-sequence wrapper, and
helpers and builders for standard script types.
"""

from __future__ import annotations

import struct
from typing import List, Optional

# ---------------------------------------------------------------------------
# Opcode constants (commonly used subset)
# ---------------------------------------------------------------------------

OP_0 = 0x00
OP_FALSE = OP_0
OP_PUSHDATA1 = 0x4C
OP_PUSHDATA2 = 0x4D
OP_PUSHDATA4 = 0x4E
OP_1NEGATE = 0x4F
OP_1 = 0x51
OP_TRUE = OP_1
OP_2 = 0x52
OP_16 = 0x60

OP_NOP = 0x61
OP_IF = 0x63
OP_NOTIF = 0x64
OP_ELSE = 0x67
OP_ENDIF = 0x68
OP_VERIFY = 0x69
OP_RETURN = 0x6A

OP_DUP = 0x76
OP_EQUAL = 0x87
OP_EQUALVERIFY = 0x88

OP_HASH160 = 0xA9
OP_CHECKSIG = 0xAC
OP_CHECKMULTISIG = 0xAE
OP_CHECKLOCKTIMEVERIFY = 0xB1
OP_CHECKSEQUENCEVERIFY = 0xB2


class CScriptNum:
    """Encode an integer in Bitcoin's script number format (CScriptNum)."""

    @staticmethod
    def encode(n: int) -> bytes:
        if n == 0:
            return b""
        negative = n < 0
        absval = abs(n)
        result = []
        while absval > 0:
            result.append(absval & 0xFF)
            absval >>= 8
        if result[-1] & 0x80:
            result.append(0x80 if negative else 0x00)
        elif negative:
            result[-1] |= 0x80
        return bytes(result)


class CScript(bytes):
    """A Bitcoin script — a sequence of opcodes and push-data operations.

    Inherits from ``bytes`` so it can be used directly as a byte string.
    """

    def __new__(cls, data: bytes = b"") -> "CScript":
        return super().__new__(cls, data)

    # -- Builders -----------------------------------------------------------

    @classmethod
    def from_ops(cls, *ops) -> "CScript":
        """Build a script from a sequence of opcodes and data pushes.

        Each element is either an int (opcode) or bytes (data push).
        """
        parts: List[bytes] = []
        for op in ops:
            if isinstance(op, int):
                parts.append(bytes([op]))
            elif isinstance(op, bytes):
                parts.append(_push_data(op))
            else:
                raise TypeError(f"Unsupported script element type: {type(op)}")
        return cls(b"".join(parts))

    # -- Classification helpers ---------------------------------------------

    def is_p2pkh(self) -> bool:
        """OP_DUP OP_HASH160 <20 bytes> OP_EQUALVERIFY OP_CHECKSIG"""
        return (
            len(self) == 25
            and self[0] == OP_DUP
            and self[1] == OP_HASH160
            and self[2] == 20
            and self[23] == OP_EQUALVERIFY
            and self[24] == OP_CHECKSIG
        )

    def is_p2sh(self) -> bool:
        """OP_HASH160 <20 bytes> OP_EQUAL"""
        return (
            len(self) == 23
            and self[0] == OP_HASH160
            and self[1] == 20
            and self[22] == OP_EQUAL
        )

    def is_witness_v0_keyhash(self) -> bool:
        """OP_0 <20 bytes>"""
        return len(self) == 22 and self[0] == OP_0 and self[1] == 20

    def is_witness_v0_scripthash(self) -> bool:
        """OP_0 <32 bytes>"""
        return len(self) == 34 and self[0] == OP_0 and self[1] == 32

    def is_witness_v1_taproot(self) -> bool:
        """OP_1 <32 bytes>"""
        return len(self) == 34 and self[0] == OP_1 and self[1] == 32

    def is_unspendable(self) -> bool:
        """Script starts with OP_RETURN."""
        return len(self) > 0 and self[0] == OP_RETURN

    def get_p2pkh_hash(self) -> Optional[bytes]:
        """Extract the 20-byte pubkey hash from a P2PKH script."""
        if self.is_p2pkh():
            return bytes(self[3:23])
        return None

    def get_p2sh_hash(self) -> Optional[bytes]:
        """Extract the 20-byte script hash from a P2SH script."""
        if self.is_p2sh():
            return bytes(self[2:22])
        return None

    # -- Standard script builders -------------------------------------------

    @classmethod
    def p2pkh(cls, pubkey_hash: bytes) -> "CScript":
        """Create a P2PKH script: OP_DUP OP_HASH160 <hash> OP_EQUALVERIFY OP_CHECKSIG."""
        assert len(pubkey_hash) == 20
        return cls(bytes([OP_DUP, OP_HASH160, 20]) + pubkey_hash + bytes([OP_EQUALVERIFY, OP_CHECKSIG]))

    @classmethod
    def p2sh(cls, script_hash: bytes) -> "CScript":
        """Create a P2SH script: OP_HASH160 <hash> OP_EQUAL."""
        assert len(script_hash) == 20
        return cls(bytes([OP_HASH160, 20]) + script_hash + bytes([OP_EQUAL]))

    @classmethod
    def p2wpkh(cls, pubkey_hash: bytes) -> "CScript":
        """Create a P2WPKH script: OP_0 <20-byte hash>."""
        assert len(pubkey_hash) == 20
        return cls(bytes([OP_0, 20]) + pubkey_hash)

    @classmethod
    def p2wsh(cls, script_hash: bytes) -> "CScript":
        """Create a P2WSH script: OP_0 <32-byte hash>."""
        assert len(script_hash) == 32
        return cls(bytes([OP_0, 32]) + script_hash)

    @classmethod
    def op_return(cls, data: bytes) -> "CScript":
        """Create an OP_RETURN script for embedding data."""
        return cls(bytes([OP_RETURN]) + _push_data(data))


def _push_data(data: bytes) -> bytes:
    """Encode a data push in script format."""
    n = len(data)
    if n == 0:
        return bytes([OP_0])
    if n <= 75:
        return bytes([n]) + data
    if n <= 0xFF:
        return bytes([OP_PUSHDATA1, n]) + data
    if n <= 0xFFFF:
        return bytes([OP_PUSHDATA2]) + struct.pack("<H", n) + data
    return bytes([OP_PUSHDATA4]) + struct.pack("<I", n) + data
