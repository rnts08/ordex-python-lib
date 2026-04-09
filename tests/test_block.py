"""
Tests for block primitives and chain parameters.
"""

import pytest

from ordex.chain.chainparams import (
    get_chain_params, oxc_mainnet, oxg_mainnet, oxg_testnet,
)
from ordex.consensus.amount import COIN
from ordex.consensus.pow import get_block_subsidy, check_proof_of_work
from ordex.core.uint256 import Uint256
from ordex.primitives.block import CBlockHeader, CBlock, compute_merkle_root, create_genesis_block


class TestCBlockHeader:
    def test_serialization_roundtrip(self):
        header = CBlockHeader(
            version=1,
            hash_prev_block=b"\x00" * 32,
            hash_merkle_root=b"\xab" * 32,
            time=1706241753,
            bits=0x1e0ffff0,
            nonce=547178,
        )
        data = header.to_bytes()
        assert len(data) == 80

        header2 = CBlockHeader.from_bytes(data)
        assert header.version == header2.version
        assert header.hash_prev_block == header2.hash_prev_block
        assert header.hash_merkle_root == header2.hash_merkle_root
        assert header.time == header2.time
        assert header.bits == header2.bits
        assert header.nonce == header2.nonce

    def test_hash_is_32_bytes(self):
        header = CBlockHeader(version=1, time=1000, bits=0x1e0ffff0, nonce=1)
        assert len(header.get_hash()) == 32

    def test_pow_hash_sha256d(self):
        header = CBlockHeader(version=1, time=1000, bits=0x1e0ffff0, nonce=1)
        assert header.get_pow_hash(use_scrypt=False) == header.get_hash()

    def test_pow_hash_scrypt(self):
        header = CBlockHeader(version=1, time=1000, bits=0x1e0ffff0, nonce=1)
        scrypt_pow = header.get_pow_hash(use_scrypt=True)
        sha_pow = header.get_pow_hash(use_scrypt=False)
        assert scrypt_pow != sha_pow  # Different algorithms, different results
        assert len(scrypt_pow) == 32


class TestMerkleRoot:
    def test_single_tx(self):
        h = b"\xab" * 32
        root = compute_merkle_root([h])
        assert root == h

    def test_two_txs(self):
        h1 = b"\x01" * 32
        h2 = b"\x02" * 32
        root = compute_merkle_root([h1, h2])
        assert len(root) == 32
        assert root != h1 and root != h2

    def test_odd_txs(self):
        """Odd count should duplicate the last hash."""
        h1 = b"\x01" * 32
        h2 = b"\x02" * 32
        h3 = b"\x03" * 32
        root = compute_merkle_root([h1, h2, h3])
        assert len(root) == 32


class TestChainParams:
    def test_oxc_mainnet_config(self):
        params = oxc_mainnet()
        assert params.name == "OrdexCoin"
        assert params.default_port == 25174
        assert params.bech32_hrp == "oxc"
        assert params.message_start == bytes([0xCC, 0xDB, 0x5C, 0x5F])
        assert params.pubkey_address_prefix == bytes([76])
        assert not params.consensus.use_scrypt
        assert not params.consensus.has_mweb

    def test_oxg_mainnet_config(self):
        params = oxg_mainnet()
        assert params.name == "OrdexGold"
        assert params.default_port == 25466
        assert params.bech32_hrp == "oxg"
        assert params.mweb_hrp == "oxgmweb"
        assert params.message_start == bytes([0x48, 0xA0, 0x22, 0xB6])
        assert params.pubkey_address_prefix == bytes([39])
        assert params.consensus.use_scrypt
        assert params.consensus.has_mweb

    def test_halving_intervals(self):
        assert oxc_mainnet().consensus.subsidy_halving_interval == 210000
        assert oxg_mainnet().consensus.subsidy_halving_interval == 239000

    def test_get_chain_params_valid(self):
        for chain_id in ["oxc_main", "oxc_test", "oxg_main", "oxg_test"]:
            params = get_chain_params(chain_id)
            assert params.name != ""

    def test_get_chain_params_invalid(self):
        with pytest.raises(ValueError):
            get_chain_params("nonexistent")

    def test_difficulty_adjustment_interval(self):
        # 7200 / 600 = 12 blocks
        oxc = oxc_mainnet()
        assert oxc.consensus.difficulty_adjustment_interval == 12

        oxg = oxg_mainnet()
        assert oxg.consensus.difficulty_adjustment_interval == 12


class TestBlockSubsidy:
    def test_oxc_genesis_reward(self):
        params = oxc_mainnet().consensus
        assert get_block_subsidy(0, params) == 20 * COIN

    def test_oxc_premine(self):
        params = oxc_mainnet().consensus
        assert get_block_subsidy(1, params) == 50000 * COIN

    def test_oxc_normal_block(self):
        params = oxc_mainnet().consensus
        assert get_block_subsidy(100, params) == 20 * COIN

    def test_oxc_first_halving(self):
        params = oxc_mainnet().consensus
        assert get_block_subsidy(210000, params) == 10 * COIN

    def test_oxg_genesis_reward(self):
        params = oxg_mainnet().consensus
        assert get_block_subsidy(0, params) == 2 * COIN

    def test_oxg_premine(self):
        params = oxg_mainnet().consensus
        assert get_block_subsidy(1, params) == 45000 * COIN

    def test_oxg_normal_block(self):
        params = oxg_mainnet().consensus
        assert get_block_subsidy(100, params) == 2 * COIN

    def test_oxg_first_halving(self):
        params = oxg_mainnet().consensus
        assert get_block_subsidy(239000, params) == 1 * COIN

    def test_subsidy_eventually_zero(self):
        params = oxc_mainnet().consensus
        assert get_block_subsidy(64 * params.subsidy_halving_interval, params) == 0


class TestPoW:
    def test_easy_target(self):
        """A zero hash should always satisfy a non-zero target."""
        pow_limit = Uint256.from_compact(0x207fffff)
        zero_hash = b"\x00" * 32
        params = oxc_mainnet().consensus
        params_copy = type(params)(**{k: getattr(params, k) for k in params.__dataclass_fields__})
        params_copy.pow_limit = pow_limit
        assert check_proof_of_work(zero_hash, 0x207fffff, params_copy)

    def test_zero_target_fails(self):
        """Zero target should always fail."""
        params = oxc_mainnet().consensus
        assert not check_proof_of_work(b"\x00" * 32, 0, params)
