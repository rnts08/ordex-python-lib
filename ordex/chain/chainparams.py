"""
Full chain parameters for all OrdexCoin and OrdexGold networks.

Provides pre-configured ChainParams instances for mainnet, testnet,
and regtest for both chains.  All values extracted from the C++ source
files: chainparams.cpp and kernel/chainparams.cpp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from ordex.consensus.params import ConsensusParams, BIP9Deployment
from ordex.core.uint256 import Uint256


@dataclass
class ChainParams:
    """Complete set of parameters defining a blockchain network."""

    # Identity
    name: str = ""
    network_id: str = ""  # "main", "test", "regtest"

    # Consensus
    consensus: ConsensusParams = field(default_factory=ConsensusParams)

    # Network
    message_start: bytes = b"\x00\x00\x00\x00"
    default_port: int = 0
    protocol_version: int = 70016
    prune_after_height: int = 0

    # Address encoding
    pubkey_address_prefix: bytes = b"\x00"      # Base58 version byte
    script_address_prefix: bytes = b"\x00"
    secret_key_prefix: bytes = b"\x00"
    ext_pubkey_prefix: bytes = b"\x00\x00\x00\x00"  # BIP32 extended pubkey
    ext_secret_prefix: bytes = b"\x00\x00\x00\x00"  # BIP32 extended secret
    bech32_hrp: str = ""
    mweb_hrp: str = ""  # OXG only

    # Genesis block data
    genesis_block_hash: str = ""
    genesis_merkle_root: str = ""
    genesis_timestamp: str = "Memento Mori"
    genesis_time: int = 0
    genesis_nonce: int = 0
    genesis_bits: int = 0
    genesis_version: int = 1
    genesis_reward: int = 0  # satoshis
    genesis_output_script: bytes = b""

    # DNS seeds
    dns_seeds: List[str] = field(default_factory=list)

    # Checkpoints
    checkpoints: dict = field(default_factory=dict)

    # Coinbase maturity
    coinbase_maturity: int = 100


# ---------------------------------------------------------------------------
# OrdexCoin (OXC) Chain Parameters
# ---------------------------------------------------------------------------

def _oxc_genesis_output_script() -> bytes:
    """The genesis coinbase output script pubkey for OXC."""
    # 65-byte uncompressed pubkey + OP_CHECKSIG
    pubkey = bytes.fromhex(
        "040184710fa689ad5023690c80f3a49c8f13f8d45b8c857fbcbc8bc4a8e4d3eb4b"
        "10f4d4604fa08dce601aaf0f470216fe1b51850b4acf21b179c45070ac7b03a9"
    )
    from ordex.core.script import OP_CHECKSIG
    return bytes([65]) + pubkey + bytes([OP_CHECKSIG])


def oxc_mainnet() -> ChainParams:
    """OrdexCoin mainnet parameters."""
    consensus = ConsensusParams(
        subsidy_halving_interval=210000,
        bip16_height=0,
        bip34_height=1,
        bip65_height=1,
        bip66_height=1,
        csv_height=1,
        segwit_height=1,
        pow_limit=Uint256.from_hex(
            "00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
        pow_target_spacing=600,       # 10 minutes
        pow_target_timespan=7200,     # 2 hours (12 blocks)
        pow_allow_min_difficulty_blocks=False,
        pow_no_retargeting=False,
        rule_change_activation_threshold=1916,
        miner_confirmation_window=2016,
        use_scrypt=False,
        has_mweb=False,
    )

    return ChainParams(
        name="OrdexCoin",
        network_id="main",
        consensus=consensus,
        message_start=bytes([0xCC, 0xDB, 0x5C, 0x5F]),
        default_port=25174,
        protocol_version=70016,
        pubkey_address_prefix=bytes([76]),     # 'X' prefix
        script_address_prefix=bytes([75]),
        secret_key_prefix=bytes([203]),
        ext_pubkey_prefix=bytes([0x04, 0x88, 0xB2, 0x1E]),
        ext_secret_prefix=bytes([0x04, 0x88, 0xAD, 0xE4]),
        bech32_hrp="oxc",
        genesis_timestamp="Memento Mori",
        genesis_time=1706241753,
        genesis_nonce=547178,
        genesis_bits=0x1e0ffff0,
        genesis_version=1,
        genesis_reward=20 * 100_000_000,
        genesis_output_script=_oxc_genesis_output_script(),
        genesis_block_hash="0000041a7dc7fc92b0aa0c21ffefea5d2e40bcb94a1c03ee975027a44e7f4dab",
        dns_seeds=[],
        coinbase_maturity=100,
    )


def oxc_testnet() -> ChainParams:
    """OrdexCoin testnet parameters."""
    consensus = ConsensusParams(
        subsidy_halving_interval=210000,
        bip16_height=0,
        bip34_height=1,
        bip65_height=1,
        bip66_height=1,
        csv_height=1,
        segwit_height=1,
        pow_limit=Uint256.from_hex(
            "00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
        pow_target_spacing=600,
        pow_target_timespan=7200,
        pow_allow_min_difficulty_blocks=True,
        pow_no_retargeting=False,
        use_scrypt=False,
        has_mweb=False,
    )

    return ChainParams(
        name="OrdexCoin Testnet",
        network_id="test",
        consensus=consensus,
        message_start=bytes([0x09, 0xEC, 0x4A, 0xE2]),
        default_port=35174,
        protocol_version=70016,
        pubkey_address_prefix=bytes([111]),
        script_address_prefix=bytes([196]),
        secret_key_prefix=bytes([239]),
        bech32_hrp="toxc",
        genesis_timestamp="Memento Mori",
        genesis_time=1706241753,
        genesis_nonce=547178,
        genesis_bits=0x1e0ffff0,
        genesis_version=1,
        genesis_reward=20 * 100_000_000,
        genesis_output_script=_oxc_genesis_output_script(),
        coinbase_maturity=100,
    )


def oxc_regtest() -> ChainParams:
    """OrdexCoin regtest parameters."""
    consensus = ConsensusParams(
        subsidy_halving_interval=150,
        bip16_height=0,
        bip34_height=1,
        bip65_height=1,
        bip66_height=1,
        csv_height=1,
        segwit_height=1,
        pow_limit=Uint256.from_hex(
            "7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
        pow_target_spacing=600,
        pow_target_timespan=7200,
        pow_allow_min_difficulty_blocks=True,
        pow_no_retargeting=True,
        use_scrypt=False,
        has_mweb=False,
    )

    return ChainParams(
        name="OrdexCoin Regtest",
        network_id="regtest",
        consensus=consensus,
        message_start=bytes([0x09, 0xEC, 0x4A, 0xE2]),
        default_port=45174,
        protocol_version=70016,
        pubkey_address_prefix=bytes([111]),
        script_address_prefix=bytes([196]),
        secret_key_prefix=bytes([239]),
        bech32_hrp="rtorc",
        genesis_timestamp="Memento Mori",
        genesis_time=1706241753,
        genesis_nonce=0,
        genesis_bits=0x207fffff,
        genesis_version=1,
        genesis_reward=20 * 100_000_000,
        genesis_output_script=_oxc_genesis_output_script(),
        coinbase_maturity=100,
    )


# ---------------------------------------------------------------------------
# OrdexGold (OXG) Chain Parameters
# ---------------------------------------------------------------------------

def _oxg_genesis_output_script() -> bytes:
    """The genesis coinbase output script pubkey for OXG."""
    pubkey = bytes.fromhex(
        "040184710fa689ad5023690c80f3a49c8f13f8d45b8c857fbcbc8bc4a8e4d3eb4b"
        "10f4d4604fa08dce601aaf0f470216fe1b51850b4acf21b179c45070ac7b03a9"
    )
    from ordex.core.script import OP_CHECKSIG
    return bytes([65]) + pubkey + bytes([OP_CHECKSIG])


def oxg_mainnet() -> ChainParams:
    """OrdexGold mainnet parameters."""
    consensus = ConsensusParams(
        subsidy_halving_interval=239000,
        bip16_height=0,
        bip34_height=1,
        bip65_height=1,
        bip66_height=1,
        csv_height=1,
        segwit_height=1,
        pow_limit=Uint256.from_hex(
            "00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
        pow_target_spacing=600,       # 10 minutes
        pow_target_timespan=7200,     # 2 hours (12 blocks)
        pow_allow_min_difficulty_blocks=False,
        pow_no_retargeting=False,
        rule_change_activation_threshold=6048,
        miner_confirmation_window=8064,
        use_scrypt=True,
        has_mweb=True,
    )

    return ChainParams(
        name="OrdexGold",
        network_id="main",
        consensus=consensus,
        message_start=bytes([0x48, 0xA0, 0x22, 0xB6]),
        default_port=25466,
        protocol_version=70017,
        pubkey_address_prefix=bytes([39]),     # 'G' prefix
        script_address_prefix=bytes([5]),
        secret_key_prefix=bytes([166]),
        ext_pubkey_prefix=bytes([0x04, 0x88, 0xB2, 0x1E]),
        ext_secret_prefix=bytes([0x04, 0x88, 0xAD, 0xE4]),
        bech32_hrp="oxg",
        mweb_hrp="oxgmweb",
        genesis_timestamp="Memento Mori",
        genesis_time=1706364693,
        genesis_nonce=1135400,
        genesis_bits=0x1e0ffff0,
        genesis_version=1,
        genesis_reward=2 * 100_000_000,
        genesis_output_script=_oxg_genesis_output_script(),
        genesis_block_hash="fe6292b96f50e25d6c08b8c2dc2e9009c8bb45ff19d4b8e91b3f4a72bc77c8bf",
        dns_seeds=[],
        coinbase_maturity=100,
    )


def oxg_testnet() -> ChainParams:
    """OrdexGold testnet parameters."""
    consensus = ConsensusParams(
        subsidy_halving_interval=239000,
        bip16_height=0,
        bip34_height=1,
        bip65_height=1,
        bip66_height=1,
        csv_height=1,
        segwit_height=1,
        pow_limit=Uint256.from_hex(
            "00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
        pow_target_spacing=600,
        pow_target_timespan=7200,
        pow_allow_min_difficulty_blocks=True,
        pow_no_retargeting=False,
        use_scrypt=True,
        has_mweb=True,
    )

    return ChainParams(
        name="OrdexGold Testnet",
        network_id="test",
        consensus=consensus,
        message_start=bytes([0xC0, 0x46, 0x1F, 0xB0]),
        default_port=35466,
        protocol_version=70017,
        pubkey_address_prefix=bytes([111]),
        script_address_prefix=bytes([196]),
        secret_key_prefix=bytes([239]),
        bech32_hrp="toxg",
        mweb_hrp="tmweb",
        genesis_timestamp="Memento Mori",
        genesis_time=1706364693,
        genesis_nonce=575050,
        genesis_bits=0x1e0ffff0,
        genesis_version=1,
        genesis_reward=2 * 100_000_000,
        genesis_output_script=_oxg_genesis_output_script(),
        coinbase_maturity=100,
    )


def oxg_regtest() -> ChainParams:
    """OrdexGold regtest parameters."""
    consensus = ConsensusParams(
        subsidy_halving_interval=150,
        bip16_height=0,
        bip34_height=1,
        bip65_height=1,
        bip66_height=1,
        csv_height=1,
        segwit_height=1,
        pow_limit=Uint256.from_hex(
            "7fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        ),
        pow_target_spacing=600,
        pow_target_timespan=7200,
        pow_allow_min_difficulty_blocks=True,
        pow_no_retargeting=True,
        use_scrypt=True,
        has_mweb=True,
    )

    return ChainParams(
        name="OrdexGold Regtest",
        network_id="regtest",
        consensus=consensus,
        message_start=bytes([0xFA, 0xBF, 0xB5, 0xDA]),
        default_port=45466,
        protocol_version=70017,
        pubkey_address_prefix=bytes([111]),
        script_address_prefix=bytes([196]),
        secret_key_prefix=bytes([239]),
        bech32_hrp="rtoxg",
        mweb_hrp="tmweb",
        genesis_timestamp="Memento Mori",
        genesis_time=1706364693,
        genesis_nonce=0,
        genesis_bits=0x207fffff,
        genesis_version=1,
        genesis_reward=2 * 100_000_000,
        genesis_output_script=_oxg_genesis_output_script(),
        coinbase_maturity=100,
    )


# ---------------------------------------------------------------------------
# Registry lookup
# ---------------------------------------------------------------------------

_CHAIN_PARAMS = {
    "oxc_main": oxc_mainnet,
    "oxc_test": oxc_testnet,
    "oxc_regtest": oxc_regtest,
    "oxg_main": oxg_mainnet,
    "oxg_test": oxg_testnet,
    "oxg_regtest": oxg_regtest,
}


def get_chain_params(chain_id: str) -> ChainParams:
    """Look up chain parameters by identifier.

    Valid identifiers: oxc_main, oxc_test, oxc_regtest,
                       oxg_main, oxg_test, oxg_regtest.
    """
    factory = _CHAIN_PARAMS.get(chain_id)
    if factory is None:
        valid = ", ".join(sorted(_CHAIN_PARAMS.keys()))
        raise ValueError(f"Unknown chain: {chain_id!r}. Valid: {valid}")
    return factory()
