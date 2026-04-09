"""
Address generation for OrdexCoin and OrdexGold.

Supports P2PKH, P2SH, Bech32 (P2WPKH), and WIF encoding.
"""

from __future__ import annotations

from ordex.chain.chainparams import ChainParams
from ordex.core.base58 import b58check_encode, bech32_encode
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


def script_to_p2sh(redeem_script: bytes, params: ChainParams) -> str:
    """Generate a P2SH address from a redeem script.

    Encodes as Base58Check with the chain's SCRIPT_ADDRESS prefix.
    """
    script_hash = hash160(redeem_script)
    return b58check_encode(params.script_address_prefix, script_hash)


def pubkey_to_bech32(pubkey: PublicKey, params: ChainParams) -> str:
    """Generate a native SegWit P2WPKH address (Bech32).

    Uses the chain's bech32 HRP:
    OXC mainnet → 'oxc1...'
    OXG mainnet → 'oxg1...'
    """
    pkh = pubkey.hash160()
    return bech32_encode(params.bech32_hrp, 0, pkh)


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
