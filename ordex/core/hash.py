"""
Cryptographic hash functions used by OrdexCoin and OrdexGold.

- sha256d: double SHA-256 (OXC PoW, both chains for txid/block-id)
- hash160: SHA-256 + RIPEMD-160 (address derivation)
- scrypt_hash: Scrypt(N=1024, r=1, p=1, dklen=32) (OXG PoW)
"""

from __future__ import annotations

import hashlib


def sha256(data: bytes) -> bytes:
    """Single SHA-256 hash."""
    return hashlib.sha256(data).digest()


def sha256d(data: bytes) -> bytes:
    """Double SHA-256 hash (SHA-256 of SHA-256).

    This is the standard hash used for Bitcoin/OrdexCoin block headers,
    transaction IDs, and Merkle trees.
    """
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def hash160(data: bytes) -> bytes:
    """RIPEMD-160(SHA-256(data)) — used for P2PKH / P2SH address derivation."""
    sha = hashlib.sha256(data).digest()
    return hashlib.new("ripemd160", sha).digest()


def scrypt_hash(header_bytes: bytes) -> bytes:
    """Scrypt hash used for OrdexGold PoW.

    Parameters match Litecoin: N=1024, r=1, p=1, dklen=32.
    The input is the serialized 80-byte block header.
    """
    return hashlib.scrypt(
        password=header_bytes,
        salt=header_bytes,
        n=1024,
        r=1,
        p=1,
        dklen=32,
    )


def merkle_hash(left: bytes, right: bytes) -> bytes:
    """Hash two Merkle tree nodes together with double-SHA-256."""
    return sha256d(left + right)
