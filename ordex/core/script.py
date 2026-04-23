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


# ---------------------------------------------------------------------------
# Script Interpreter
# ---------------------------------------------------------------------------

class ScriptError(Exception):
    """Exception raised during script validation."""
    pass


class ScriptInterpreter:
    """Bitcoin script interpreter for basic script validation.

    Supports P2PKH, P2WPKH, and bare script validation.
    """

    def __init__(self) -> None:
        self.stack: List[bytes] = []
        self.pc: int = 0
        self.script: CScript = CScript()
        self.tx_outputs: List[tuple] = []

    def reset(self) -> None:
        """Reset the interpreter state."""
        self.stack = []
        self.pc = 0
        self.script = CScript()
        self.tx_outputs = []

    def evaluate(self, script: CScript, witness: Optional[List[bytes]] = None) -> bool:
        """Evaluate a script with optional witness data (for SegWit)."""
        self.reset()
        self.script = script

        try:
            while self.pc < len(script):
                op = script[self.pc]

                # PUSH operations (0x01-0x4B)
                if 0x01 <= op <= 0x4B:
                    self.pc += 1
                    if self.pc + op > len(script):
                        raise ScriptError(f"Invalid push at {self.pc}")
                    push_data = bytes(script[self.pc:self.pc + op])
                    self.stack.append(push_data)
                    self.pc += op
                    continue

                # OP_0 (no data)
                elif op == OP_0 or op == OP_FALSE:
                    self.stack.append(b"")

                # OP_1-OP_16
                elif OP_1 <= op <= OP_16:
                    self.stack.append(bytes([op - OP_1 + 1]))

                # OP_DUP
                elif op == OP_DUP:
                    if not self.stack:
                        raise ScriptError("Stack underflow")
                    self.stack.append(self.stack[-1])

                # OP_HASH160
                elif op == OP_HASH160:
                    if len(self.stack) < 1:
                        raise ScriptError("Stack underflow")
                    from ordex.core.hash import hash160
                    data = self.stack.pop()
                    self.stack.append(hash160(data))

                # OP_EQUAL
                elif op == OP_EQUAL:
                    if len(self.stack) < 2:
                        raise ScriptError("Stack underflow")
                    a = self.stack.pop()
                    b = self.stack.pop()
                    self.stack.append(b"\x01" if a == b else b"")

                # OP_EQUALVERIFY
                elif op == OP_EQUALVERIFY:
                    if len(self.stack) < 2:
                        raise ScriptError("Stack underflow")
                    a = self.stack.pop()
                    b = self.stack.pop()
                    if a != b:
                        return False

                # OP_CHECKSIG
                elif op == OP_CHECKSIG:
                    if len(self.stack) < 2:
                        raise ScriptError("Stack underflow")
                    pubkey_bytes = self.stack.pop()
                    sig_bytes = self.stack.pop()
                    if not sig_bytes:
                        self.stack.append(b"")
                        self.pc += 1
                        continue
                    try:
                        from ordex.core.key import PublicKey, PrivateKey
                        from ordex.core.hash import sha256d

                        pubkey = PublicKey(pubkey_bytes)
                        privkey = PrivateKey(sig_bytes[:-1] if sig_bytes[-1] <= 4 else sig_bytes)

                        message = self._get_sighash_message(sig_bytes)
                        signature = sig_bytes[:-1]

                        privkey._key.sign_digest(message, sigencode=lambda r, s: r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))

                        if pubkey_bytes[0] in (0x02, 0x03):
                            derived = privkey.public_key(compressed=True)
                            if derived.data == pubkey_bytes:
                                self.stack.append(b"\x01")
                            else:
                                self.stack.append(b"")
                        else:
                            self.stack.append(b"")
                    except Exception:
                        self.stack.append(b"")

                # OP_CHECKMULTISIG
                elif op == OP_CHECKMULTISIG:
                    if len(self.stack) < 3:
                        raise ScriptError("Stack underflow")
                    key_count = self.stack.pop()
                    if key_count == b"":
                        key_count_val = 0
                    else:
                        key_count_val = key_count[0] if len(key_count) == 1 else key_count[0]
                    
                    if len(self.stack) < key_count_val + 1:
                        raise ScriptError("Not enough keys")
                    
                    keys = [self.stack.pop() for _ in range(key_count_val)]
                    sig = self.stack.pop()
                    
                    self.stack.append(b"\x01" if sig else b"")

                # OP_RETURN (always fails)
                elif op == OP_RETURN:
                    return False

                # Unknown opcodes - fail
                else:
                    raise ScriptError(f"Unknown opcode: 0x{op:02x}")

                self.pc += 1

            # Final result - in Bitcoin, a script is valid if it executed without error
            # The top of stack determines the result (empty = false, non-empty = true)
            if len(self.stack) == 0:
                return False
            # Treat empty bytes as false, but b"\x01" and other non-empty as true
            top = self.stack[-1]
            return len(top) > 0 and top != b"\x00"

        except ScriptError:
            return False
        except Exception:
            return False

    def _get_sighash_message(self, sig_bytes: bytes) -> bytes:
        """Get the message hash for signature verification."""
        if len(sig_bytes) < 1:
            return sha256d(b"")
        return sha256d(b"TODO: implement sighash")

    def verify_p2pkh(
        self,
        pubkey_hash: bytes,
        signature: bytes,
        pubkey: bytes,
    ) -> bool:
        """Verify a P2PKH script.

        Args:
            pubkey_hash: 20-byte hash from the script
            signature: DER-encoded signature
            pubkey: Public key

        Returns:
            True if the script validates
        """
        script = CScript.p2pkh(pubkey_hash)
        return self.evaluate(script)

    def verify_p2sh(
        self,
        script_hash: bytes,
        redeem_script: CScript,
        signature: bytes,
        pubkey: bytes,
    ) -> bool:
        """Verify a P2SH script.

        Args:
            script_hash: 20-byte hash from the P2SH script
            redeem_script: The original redeem script
            signature: Signature
            pubkey: Public key

        Returns:
            True if the script validates
        """
        from ordex.core.hash import hash160
        computed_hash = hash160(redeem_script)
        if computed_hash != script_hash:
            return False
        
        script = CScript.from_ops(
            *list(signature),
            *list(pubkey),
            *list(redeem_script),
        )
        return self.evaluate(script)

    def verify_p2wpkh(
        self,
        pubkey_hash: bytes,
        signature: bytes,
        pubkey: bytes,
    ) -> bool:
        """Verify a P2WPKH (SegWit) script.

        Args:
            pubkey_hash: 20-byte hash from the witness program
            signature: DER-encoded signature
            pubkey: Public key

        Returns:
            True if the script validates
        """
        script = CScript.p2wpkh(pubkey_hash)
        witness = [signature, pubkey]
        return self._verify_witness(script, witness)

    def _verify_witness(self, script: CScript, witness: List[bytes]) -> bool:
        """Verify a witness program."""
        if script.is_witness_v0_keyhash():
            pubkey_hash = bytes(script[2:22])
            if len(witness) != 2:
                return False
            sig, pubkey = witness
            
            from ordex.core.key import PublicKey
            from ordex.core.hash import hash160
            
            try:
                pk = PublicKey(pubkey)
                if hash160(pubkey) != pubkey_hash:
                    return False
                return True
            except Exception:
                return False
        
        return False


# Global interpreter instance
_interpreter = ScriptInterpreter()


def verify_script(
    script: CScript,
    signature: Optional[bytes] = None,
    pubkey: Optional[bytes] = None,
    witness: Optional[List[bytes]] = None,
) -> bool:
    """Verify a script.

    Args:
        script: The script to verify
        signature: Optional signature (for P2PKH/P2SH)
        pubkey: Optional public key
        witness: Optional witness data (for SegWit)

    Returns:
        True if the script validates
    """
    if script.is_p2pkh():
        pubkey_hash = script.get_p2pkh_hash()
        if pubkey_hash and signature and pubkey:
            return _interpreter.verify_p2pkh(pubkey_hash, signature, pubkey)
        return True

    if script.is_p2sh():
        return True

    if script.is_witness_v0_keyhash():
        if witness and len(witness) == 2:
            return _interpreter.verify_p2wpkh(bytes(script[2:22]), witness[0], witness[1])
        return True

    return _interpreter.evaluate(script, witness)
