"""
BIP39 mnemonic to seed implementation.

Minimal implementation for deriving a seed from a BIP39 mnemonic phrase.
"""

from __future__ import annotations

import hashlib
import unicodedata


def mnemonic_to_seed(mnemonic: str, passphrase: str = "") -> bytes:
    """Derive a seed from a BIP39 mnemonic phrase using PBKDF2.

    Args:
        mnemonic: BIP39 mnemonic phrase (12-24 words)
        passphrase: Optional passphrase for extra security

    Returns:
        64-byte seed suitable for BIP32 HD wallet

    Raises:
        ValueError: If mnemonic is empty
    """
    if not mnemonic:
        raise ValueError("Mnemonic cannot be empty")

    # Normalize to NFKD (Unicode Normalization Form Compatibility Decomposition)
    mnemonic_normalized = unicodedata.normalize("NFKD", mnemonic)
    passphrase_normalized = unicodedata.normalize("NFKD", passphrase)

    # Salt = "mnemonic" + passphrase
    salt = ("mnemonic" + passphrase_normalized).encode("utf-8")

    # PBKDF2 with SHA512, 2048 iterations, 64 byte output
    seed = hashlib.pbkdf2_hmac(
        "sha512",
        mnemonic_normalized.encode("utf-8"),
        salt,
        2048,
        dklen=64,
    )

    return seed