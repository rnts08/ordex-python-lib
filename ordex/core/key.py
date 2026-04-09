"""
ECDSA key handling for secp256k1.

Provides private/public key generation, WIF encoding/decoding, and
public key compression.  Uses the ``ecdsa`` library.
"""

from __future__ import annotations

import os
from typing import Optional

import ecdsa

from ordex.core.base58 import b58check_encode, b58check_decode
from ordex.core.hash import hash160


# secp256k1 curve object
SECP256K1 = ecdsa.SECP256k1


class PrivateKey:
    """A secp256k1 private key (32-byte scalar)."""

    __slots__ = ("_key",)

    def __init__(self, secret: bytes) -> None:
        if len(secret) != 32:
            raise ValueError(f"Private key must be 32 bytes, got {len(secret)}")
        self._key = ecdsa.SigningKey.from_string(secret, curve=SECP256K1)

    @classmethod
    def generate(cls) -> "PrivateKey":
        """Generate a new random private key."""
        return cls(os.urandom(32))

    @classmethod
    def from_wif(cls, wif: str) -> "PrivateKey":
        """Decode a WIF-encoded private key."""
        version, payload = b58check_decode(wif)
        # payload is 32 bytes, or 33 bytes with 0x01 compressed flag
        if len(payload) == 33 and payload[-1] == 0x01:
            return cls(payload[:32])
        if len(payload) == 32:
            return cls(payload)
        raise ValueError(f"Invalid WIF payload length: {len(payload)}")

    @property
    def secret(self) -> bytes:
        """Raw 32-byte secret scalar."""
        return self._key.to_string()

    def to_wif(self, secret_key_prefix: int = 0xCB, compressed: bool = True) -> str:
        """Encode as WIF string.

        Args:
            secret_key_prefix: The chain-specific SECRET_KEY byte
                (OXC mainnet=203/0xCB, OXG mainnet=166/0xA6).
            compressed: Whether to flag the key as compressed.
        """
        payload = self.secret
        if compressed:
            payload += b"\x01"
        return b58check_encode(bytes([secret_key_prefix]), payload)

    def public_key(self, compressed: bool = True) -> "PublicKey":
        """Derive the corresponding public key."""
        vk = self._key.get_verifying_key()
        point = vk.pubkey.point
        return PublicKey.from_point(point.x(), point.y(), compressed=compressed)

    def sign(self, message_hash: bytes) -> bytes:
        """Sign a 32-byte hash, returning a DER-encoded signature."""
        return self._key.sign_digest(
            message_hash,
            sigencode=ecdsa.util.sigencode_der,
        )


class PublicKey:
    """A secp256k1 public key (compressed or uncompressed)."""

    __slots__ = ("_data",)

    def __init__(self, data: bytes) -> None:
        if len(data) == 33:
            if data[0] not in (0x02, 0x03):
                raise ValueError("Invalid compressed public key prefix")
        elif len(data) == 65:
            if data[0] != 0x04:
                raise ValueError("Invalid uncompressed public key prefix")
        else:
            raise ValueError(f"Invalid public key length: {len(data)}")
        self._data = data

    @classmethod
    def from_point(cls, x: int, y: int, compressed: bool = True) -> "PublicKey":
        """Create from curve point coordinates."""
        if compressed:
            prefix = 0x02 if y % 2 == 0 else 0x03
            return cls(bytes([prefix]) + x.to_bytes(32, "big"))
        return cls(b"\x04" + x.to_bytes(32, "big") + y.to_bytes(32, "big"))

    @property
    def data(self) -> bytes:
        """Raw serialized public key bytes."""
        return self._data

    @property
    def is_compressed(self) -> bool:
        return len(self._data) == 33

    def hash160(self) -> bytes:
        """RIPEMD-160(SHA-256(pubkey)) — the 20-byte pubkey hash."""
        return hash160(self._data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PublicKey):
            return self._data == other._data
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._data)

    def __repr__(self) -> str:
        return f"PublicKey({self._data.hex()})"
