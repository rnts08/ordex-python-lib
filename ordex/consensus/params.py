"""
Consensus parameters.

Defines the ConsensusParams dataclass holding all consensus-critical
configuration for a chain: PoW limits, halving schedule, BIP activation
heights, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from ordex.core.uint256 import Uint256


@dataclass
class BIP9Deployment:
    """BIP9 version-bits deployment configuration."""
    bit: int = 28
    start_time: int = -2  # NEVER_ACTIVE
    timeout: int = -2
    min_activation_height: int = 0
    # OXG-style height-based activation
    start_height: int = 0
    timeout_height: int = 0

    # Constants
    NO_TIMEOUT: int = field(default=2**63 - 1, init=False)
    ALWAYS_ACTIVE: int = field(default=-1, init=False)
    NEVER_ACTIVE: int = field(default=-2, init=False)


@dataclass
class ConsensusParams:
    """All consensus-critical parameters for a chain."""

    # Genesis
    hash_genesis_block: bytes = b"\x00" * 32

    # Subsidy
    subsidy_halving_interval: int = 210000

    # BIP activation heights
    bip16_height: int = 0
    bip34_height: int = 0
    bip34_hash: bytes = b"\x00" * 32
    bip65_height: int = 0
    bip66_height: int = 0
    csv_height: int = 0
    segwit_height: int = 0
    min_bip9_warning_height: int = 0

    # Version bits
    rule_change_activation_threshold: int = 1916
    miner_confirmation_window: int = 2016
    deployments: Dict[str, BIP9Deployment] = field(default_factory=dict)

    # Proof of work
    pow_limit: Uint256 = field(default_factory=lambda: Uint256.from_hex(
        "00000fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    ))
    pow_allow_min_difficulty_blocks: bool = False
    pow_no_retargeting: bool = False
    pow_target_spacing: int = 600  # seconds (10 minutes)
    pow_target_timespan: int = 7200  # seconds (120 minutes / 2 hours)

    # Chain work
    minimum_chain_work: Uint256 = field(default_factory=lambda: Uint256(0))
    default_assume_valid: Uint256 = field(default_factory=lambda: Uint256(0))

    # Signet
    signet_blocks: bool = False
    signet_challenge: bytes = b""

    # MWEB (OXG only)
    has_mweb: bool = False

    # Hashing algorithm
    use_scrypt: bool = False  # True for OXG, False for OXC

    @property
    def difficulty_adjustment_interval(self) -> int:
        """Number of blocks between difficulty retargets."""
        return self.pow_target_timespan // self.pow_target_spacing
