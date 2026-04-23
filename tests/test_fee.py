"""
Tests for fee estimation.
"""

import pytest

from ordex.consensus.fee import (
    FeeEstimator, FeeEstimate,
    calculate_vbytes_from_weight, calculate_fee_from_rate,
)


class TestFeeEstimator:
    """Tests for FeeEstimator class."""

    def test_init(self):
        estimator = FeeEstimator()
        assert estimator.rpc is None

    def test_init_with_rpc(self):
        class MockRpc:
            def estimatesmartfee(self, target):
                return {"feerate": 8.5, "blocks": target}

        estimator = FeeEstimator(rpc_client=MockRpc())
        assert estimator.rpc is not None

    def test_local_estimate_high_priority(self):
        estimator = FeeEstimator()
        result = estimator.estimate_smart_fee(conf_target=2)

        assert result.feerate == 10.0
        assert result.blocks == 2

    def test_local_estimate_medium_priority(self):
        estimator = FeeEstimator()
        result = estimator.estimate_smart_fee(conf_target=4)

        assert result.feerate == 5.0

    def test_local_estimate_low_priority(self):
        estimator = FeeEstimator()
        result = estimator.estimate_smart_fee(conf_target=8)

        assert result.feerate == 1.0

    def test_local_estimate_minimum(self):
        estimator = FeeEstimator()
        result = estimator.estimate_smart_fee(conf_target=100)

        assert result.feerate == 0.1

    def test_economical_mode_reduces_fee(self):
        estimator = FeeEstimator()
        
        conservative = estimator.estimate_smart_fee(conf_target=2, estimate_mode="conservative")
        economical = estimator.estimate_smart_fee(conf_target=2, estimate_mode="economical")

        assert economical.feerate < conservative.feerate

    def test_get_fee_for_transaction(self):
        estimator = FeeEstimator()
        fee = estimator.get_fee_for_transaction(tx_size=500, conf_target=4)

        assert fee > 0

    def test_get_minimum_fee(self):
        estimator = FeeEstimator()
        fee = estimator.get_minimum_fee(tx_size=200)

        assert fee >= 50

    def test_rpc_fallback(self):
        class FailingRpc:
            def estimatesmartfee(self, target):
                raise ConnectionError("No connection")

        estimator = FeeEstimator(rpc_client=FailingRpc())
        result = estimator.estimate_smart_fee(conf_target=6)

        assert isinstance(result, FeeEstimate)
        assert result.feerate > 0


class TestFeeUtilities:
    """Tests for fee utility functions."""

    def test_calculate_vbytes_from_weight(self):
        assert calculate_vbytes_from_weight(4000) == 1000
        assert calculate_vbytes_from_weight(4001) == 1001
        assert calculate_vbytes_from_weight(1) == 1
        assert calculate_vbytes_from_weight(0) == 0

    def test_calculate_fee_from_rate(self):
        fee = calculate_fee_from_rate(1000, 5.0)
        assert fee == 5000

    def test_calculate_fee_from_rate_rounds_down(self):
        fee = calculate_fee_from_rate(101, 5.0)
        assert fee == 505


class TestFeeEstimate:
    """Tests for FeeEstimate dataclass."""

    def test_fee_estimate_creation(self):
        estimate = FeeEstimate(
            feerate=5.0,
            estimate="conservative",
            blocks=6,
        )

        assert estimate.feerate == 5.0
        assert estimate.estimate == "conservative"
        assert estimate.blocks == 6