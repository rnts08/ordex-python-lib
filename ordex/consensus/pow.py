"""
Proof-of-work validation, difficulty retargeting, and block subsidy.

Implements the PoW rules for both OrdexCoin (Bitcoin-style) and
OrdexGold (Litecoin-style with Art Forz fix and overflow shift).
"""

from __future__ import annotations

from ordex.consensus.amount import COIN
from ordex.consensus.params import ConsensusParams
from ordex.core.uint256 import Uint256


def check_proof_of_work(pow_hash: bytes, nbits: int, params: ConsensusParams) -> bool:
    """Validate that a PoW hash meets the claimed difficulty target.

    Args:
        pow_hash: The PoW hash (SHA-256d for OXC, Scrypt for OXG), internal byte order.
        nbits: The compact target from the block header.
        params: Consensus parameters (for pow_limit).

    Returns:
        True if the hash satisfies the target.
    """
    target = Uint256.from_compact(nbits)

    # Check range
    if target == 0:
        return False
    if target > params.pow_limit:
        return False

    # Check PoW
    hash_value = Uint256.from_bytes_le(pow_hash)
    return hash_value <= target


def calculate_next_work_required_bitcoin(
    last_nbits: int,
    first_block_time: int,
    last_block_time: int,
    params: ConsensusParams,
) -> int:
    """Standard Bitcoin/OXC difficulty retarget calculation.

    Adjusts difficulty based on actual vs expected timespan,
    clamped to [timespan/4, timespan*4].
    """
    if params.pow_no_retargeting:
        return last_nbits

    actual_timespan = last_block_time - first_block_time

    # Clamp
    if actual_timespan < params.pow_target_timespan // 4:
        actual_timespan = params.pow_target_timespan // 4
    if actual_timespan > params.pow_target_timespan * 4:
        actual_timespan = params.pow_target_timespan * 4

    pow_limit = params.pow_limit

    # Retarget
    bn_new = Uint256.from_compact(last_nbits)
    bn_new = bn_new * actual_timespan
    bn_new = bn_new / params.pow_target_timespan

    if bn_new > pow_limit:
        bn_new = pow_limit

    return bn_new.get_compact()


def calculate_next_work_required_litecoin(
    last_nbits: int,
    first_block_time: int,
    last_block_time: int,
    params: ConsensusParams,
) -> int:
    """OrdexGold / Litecoin difficulty retarget with overflow fix.

    Includes the intermediate uint256 overflow bit-shift guard (Art Forz fix).
    """
    if params.pow_no_retargeting:
        return last_nbits

    actual_timespan = last_block_time - first_block_time

    # Clamp
    if actual_timespan < params.pow_target_timespan // 4:
        actual_timespan = params.pow_target_timespan // 4
    if actual_timespan > params.pow_target_timespan * 4:
        actual_timespan = params.pow_target_timespan * 4

    pow_limit = params.pow_limit

    bn_new = Uint256.from_compact(last_nbits)

    # OXG overflow fix: shift down if bits would overflow
    shift = bn_new.bits() > pow_limit.bits() - 1
    if shift:
        bn_new = bn_new >> 1

    bn_new = bn_new * actual_timespan
    bn_new = bn_new / params.pow_target_timespan

    if shift:
        bn_new = bn_new << 1

    if bn_new > pow_limit:
        bn_new = pow_limit

    return bn_new.get_compact()


def get_block_subsidy(height: int, params: ConsensusParams) -> int:
    """Calculate the block reward (subsidy) for a given height.

    Both OXC and OXG use the same structure:
    - Block 1: large premine
    - All other blocks: standard reward
    - Reward halves every ``subsidy_halving_interval`` blocks.

    Returns:
        Block subsidy in satoshis.
    """
    halvings = height // params.subsidy_halving_interval

    # Force reward to zero when right-shift is undefined
    if halvings >= 64:
        return 0

    if params.use_scrypt:
        # OrdexGold
        if height == 1:
            base = 45000
        else:
            base = 2
    else:
        # OrdexCoin
        if height == 1:
            base = 50000
        else:
            base = 20

    subsidy = base * COIN
    subsidy >>= halvings
    return subsidy
