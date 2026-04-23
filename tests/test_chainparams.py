"""
Tests for chain parameters completeness.
"""

import pytest

from ordex.chain.chainparams import (
    oxc_mainnet, oxc_testnet, oxc_regtest,
    oxg_mainnet, oxg_testnet, oxg_regtest,
)


class TestChainParamsComplete:
    """Test that all chain params have complete genesis info."""

    def test_oxc_mainnet_complete(self):
        params = oxc_mainnet()
        assert params.genesis_block_hash != ""
        assert len(params.genesis_block_hash) == 64

    def test_oxc_testnet_complete(self):
        params = oxc_testnet()
        assert params.genesis_block_hash != ""
        assert len(params.genesis_block_hash) == 64

    def test_oxc_regtest_complete(self):
        params = oxc_regtest()
        assert params.genesis_block_hash != ""
        assert len(params.genesis_block_hash) == 64

    def test_oxg_mainnet_complete(self):
        params = oxg_mainnet()
        assert params.genesis_block_hash != ""
        assert len(params.genesis_block_hash) == 64

    def test_oxg_testnet_complete(self):
        params = oxg_testnet()
        assert params.genesis_block_hash != ""
        assert len(params.genesis_block_hash) == 64

    def test_oxg_regtest_complete(self):
        params = oxg_regtest()
        assert params.genesis_block_hash != ""
        assert len(params.genesis_block_hash) == 64


class TestChainParamsNetworkID:
    """Test network ID settings."""

    def test_oxc_mainnet_network(self):
        params = oxc_mainnet()
        assert params.network_id == "main"

    def test_oxc_testnet_network(self):
        params = oxc_testnet()
        assert params.network_id == "test"

    def test_oxc_regtest_network(self):
        params = oxc_regtest()
        assert params.network_id == "regtest"

    def test_oxg_mainnet_network(self):
        params = oxg_mainnet()
        assert params.network_id == "main"

    def test_oxg_testnet_network(self):
        params = oxg_testnet()
        assert params.network_id == "test"

    def test_oxg_regtest_network(self):
        params = oxg_regtest()
        assert params.network_id == "regtest"


class TestChainParamsAddresses:
    """Test address prefixes."""

    def test_oxc_mainnet_address_prefix(self):
        params = oxc_mainnet()
        assert params.pubkey_address_prefix[0] == 76  # 'X'

    def test_oxg_mainnet_address_prefix(self):
        params = oxg_mainnet()
        assert params.pubkey_address_prefix[0] == 39  # 'G'

    def test_testnet_address_prefix(self):
        for params in [oxc_testnet(), oxg_testnet()]:
            assert params.pubkey_address_prefix[0] == 111  # 'm' or 'n'

    def test_regtest_address_prefix(self):
        for params in [oxc_regtest(), oxg_regtest()]:
            assert params.pubkey_address_prefix[0] == 111


class TestChainParamsBech32:
    """Test Bech32 HRP settings."""

    def test_oxc_bech32_hrp(self):
        params = oxc_mainnet()
        assert params.bech32_hrp == "oxc"

    def test_oxg_bech32_hrp(self):
        params = oxg_mainnet()
        assert params.bech32_hrp == "oxg"

    def test_testnet_bech32_hrp(self):
        params = oxc_testnet()
        assert params.bech32_hrp == "toxc"

    def test_regtest_bech32_hrp(self):
        params = oxc_regtest()
        assert params.bech32_hrp == "rtorc"