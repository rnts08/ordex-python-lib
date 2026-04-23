"""
Address generation for OrdexCoin and OrdexGold.

Supports P2PKH, P2SH, Bech32 (P2WPKH), and WIF encoding.
"""

from __future__ import annotations

from typing import Optional, Tuple

from ordex.chain.chainparams import ChainParams
from ordex.core.base58 import b58check_encode, b58check_decode, bech32_encode, bech32_decode
from ordex.core.hash import hash160
from ordex.core.key import PrivateKey, PublicKey


def pubkey_to_p2pkh(pubkey: PublicKey, params: ChainParams) -> str:
    """Generate a P2PKH address from a public key.

    Encodes as Base58Check with the chain's PUBKEY_ADDRESS prefix.
    OXC mainnet → 'X' prefix (version 76)
    OXG mainnet → 'G' prefix (version 39)
    """
    pkh = pubkey.hash160()
    return b58check_encode(params.pubkey_address_prefix, pkh)


def p2pkh_to_pubkey_hash(address: str) -> Tuple[bytes, bytes]:
    """Decode a P2PKH address to extract the version byte and pubkey hash.

    Returns (version_byte, pubkey_hash).

    Raises ValueError if the address is invalid.
    """
    version, payload = b58check_decode(address)
    if len(payload) != 20:
        raise ValueError(f"P2PKH address payload must be 20 bytes, got {len(payload)}")
    return version, payload


def script_to_p2sh(redeem_script: bytes, params: ChainParams) -> str:
    """Generate a P2SH address from a redeem script.

    Encodes as Base58Check with the chain's SCRIPT_ADDRESS prefix.
    """
    script_hash = hash160(redeem_script)
    return b58check_encode(params.script_address_prefix, script_hash)


def p2sh_to_script_hash(address: str) -> Tuple[bytes, bytes]:
    """Decode a P2SH address to extract the version byte and script hash.

    Returns (version_byte, script_hash).

    Raises ValueError if the address is invalid.
    """
    version, payload = b58check_decode(address)
    if len(payload) != 20:
        raise ValueError(f"P2SH address payload must be 20 bytes, got {len(payload)}")
    return version, payload


def pubkey_to_bech32(pubkey: PublicKey, params: ChainParams) -> str:
    """Generate a native SegWit P2WPKH address (Bech32).

    Uses the chain's bech32 HRP:
    OXC mainnet → 'oxc1...'
    OXG mainnet → 'oxg1...'
    """
    pkh = pubkey.hash160()
    return bech32_encode(params.bech32_hrp, 0, pkh)


def bech32_to_pubkey_hash(address: str) -> Tuple[str, int, bytes]:
    """Decode a Bech32/P2WPKH address.

    Returns (hrp, witness_version, witness_program).

    Raises ValueError if the address is invalid.
    """
    hrp, witver, witprog = bech32_decode(address)
    if witver != 0:
        raise ValueError(f"Only witness version 0 supported, got {witver}")
    if len(witprog) != 20:
        raise ValueError(f"P2WPKH witness program must be 20 bytes, got {len(witprog)}")
    return hrp, witver, witprog


def decode_address(address: str) -> dict:
    """Decode any address type and return a dict with details.

    Detects address type (P2PKH, P2SH, Bech32) and decodes accordingly.

    Returns a dict with:
        - type: 'p2pkh', 'p2sh', 'bech32', or 'unknown'
        - version: version byte (for Base58)
        - hash: the 20-byte hash (pubkey or script)
        - hrp: for Bech32 addresses
        - chain: detected chain hint based on prefix/HRP
    """
    result = {
        "type": "unknown",
        "address": address,
    }

    # Try Bech32 first (lowercase, starts with oxc1, oxg1, etc.)
    if address.lower().startswith(("oxc1", "oxg1", "toxc1", "toxg1", "rtoxc1", "rtoxg1", "rtorc1")):
        try:
            hrp, witver, witprog = bech32_to_pubkey_hash(address)
            result["type"] = "bech32"
            result["hrp"] = hrp
            result["witness_version"] = witver
            result["hash"] = witprog
            return result
        except ValueError:
            pass

    # Try Base58Check (P2PKH or P2SH)
    try:
        version, payload = b58check_decode(address)
        if len(payload) == 20:
            result["type"] = "p2pkh"
            result["version"] = version
            result["hash"] = payload
            return result
    except (ValueError, Exception):
        pass

    return result


def privkey_to_wif(privkey: PrivateKey, params: ChainParams, compressed: bool = True) -> str:
    """Encode a private key in WIF format with the chain's SECRET_KEY prefix."""
    return privkey.to_wif(
        secret_key_prefix=params.secret_key_prefix[0],
        compressed=compressed,
    )


def generate_keypair(params: ChainParams):
    """Generate a new keypair and return (private_key, public_key, addresses).

    Returns a dict with:
    - 'privkey': PrivateKey object
    - 'pubkey': PublicKey object
    - 'wif': WIF-encoded private key
    - 'p2pkh': P2PKH address
    - 'p2wpkh': Bech32 P2WPKH address
    """
    privkey = PrivateKey.generate()
    pubkey = privkey.public_key(compressed=True)
    return {
        "privkey": privkey,
        "pubkey": pubkey,
        "wif": privkey_to_wif(privkey, params),
        "p2pkh": pubkey_to_p2pkh(pubkey, params),
        "p2wpkh": pubkey_to_bech32(pubkey, params),
    }