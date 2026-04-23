"""
Fee estimation for transactions.

Provides local fee estimation based on transaction size and
historical fee data when RPC is unavailable.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FeeEstimate:
    """Fee estimation result."""
    feerate: float  # satoshis per vbyte
    estimate: str  # "conservative", "economical", "unreasonable"
    blocks: int  # estimated confirmation blocks


class FeeEstimator:
    """Local fee estimation based on mempool data and presets.

    When connected to a node, can use RPC estimates.
    When offline, uses preset fee levels.
    """

    DEFAULT_FEES = {
        "high": 10.0,      # ~10 sat/vbyte, ~10 min confirmation
        "medium": 5.0,     # ~5 sat/vbyte, ~30 min confirmation  
        "low": 1.0,        # ~1 sat/vbyte, ~1 hour confirmation
        "minimum": 0.1,    # ~0.1 sat/vbyte, ~1 day confirmation
    }

    def __init__(self, rpc_client=None) -> None:
        self.rpc = rpc_client
        self._cached_estimates: Dict[int, FeeEstimate] = {}
        self._last_update: Optional[int] = None

    def estimate_smart_fee(
        self,
        conf_target: int = 6,
        estimate_mode: str = "conservative",
    ) -> FeeEstimate:
        """Estimate fees for confirmation within target blocks.

        Args:
            conf_target: Target number of blocks for confirmation
            estimate_mode: "conservative" or "economical"

        Returns:
            FeeEstimate with feerate in sat/vbyte
        """
        if self.rpc:
            try:
                result = self.rpc.estimatesmartfee(conf_target)
                feerate = result.get("feerate", 0)
                return FeeEstimate(
                    feerate=feerate,
                    estimate=estimate_mode,
                    blocks=result.get("blocks", conf_target),
                )
            except Exception:
                pass

        return self._get_local_estimate(conf_target, estimate_mode)

    def _get_local_estimate(
        self,
        conf_target: int,
        estimate_mode: str,
    ) -> FeeEstimate:
        """Get local fee estimate based on target blocks."""
        if conf_target <= 2:
            feerate = self.DEFAULT_FEES["high"]
        elif conf_target <= 4:
            feerate = self.DEFAULT_FEES["medium"]
        elif conf_target <= 10:
            feerate = self.DEFAULT_FEES["low"]
        else:
            feerate = self.DEFAULT_FEES["minimum"]

        if estimate_mode == "economical":
            feerate = feerate * 0.8

        return FeeEstimate(
            feerate=feerate,
            estimate=estimate_mode,
            blocks=conf_target,
        )

    def get_fee_for_transaction(
        self,
        tx_size: int,
        conf_target: int = 6,
    ) -> int:
        """Calculate estimated fee for a transaction.

        Args:
            tx_size: Transaction size in bytes
            conf_target: Target confirmation blocks

        Returns:
            Fee in satoshis
        """
        estimate = self.estimate_smart_fee(conf_target)
        fee_vbytes = (tx_size + 3) // 4
        return int(estimate.feerate * fee_vbytes)

    def get_minimum_fee(self, tx_size: int) -> int:
        """Get the minimum safe fee for a transaction.
        
        Uses the network's default minimum relay fee.
        """
        default_min_rate = 1.0
        fee_vbytes = (tx_size + 3) // 4
        return int(default_min_rate * fee_vbytes)


def calculate_vbytes_from_weight(weight: int) -> int:
    """Calculate vsize (virtual bytes) from weight units.
    
    Bitcoin uses weight units where:
    - Legacy bytes: 4 weight units
    - SegWit bytes: 1 weight unit
    vbytes = (weight + 3) // 4
    """
    return (weight + 3) // 4


def calculate_fee_from_rate(tx_size: int, feerate: float) -> int:
    """Calculate fee given transaction size and feerate.
    
    Args:
        tx_size: Transaction size in bytes
        feerate: Fee rate in sat/vbyte
    
    Returns:
        Fee in satoshis
    """
    return int(tx_size * feerate)