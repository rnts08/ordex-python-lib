"""
Tests for BIP32/39 HD Wallet implementation.
"""

import hmac
import pytest

from ordex.chain.chainparams import oxc_mainnet, oxg_mainnet, oxc_testnet, oxg_testnet
from ordex.wallet.hd import (
    BIP32Path, ExtendedKey, HDWallet,
    BIP32_VERSION_MAINNET_PUB, BIP32_VERSION_MAINNET_PRIV,
    BIP32_VERSION_TESTNET_PUB, BIP32_VERSION_TESTNET_PRIV,
)
from ordex.wallet.bip39 import mnemonic_to_seed
from ordex.core.key import PrivateKey, PublicKey


class TestBIP32Path:
    """Tests for BIP32Path parsing."""

    def test_parse_simple_path(self):
        path = BIP32Path("m/0")
        assert path.path == "m/0"
        assert path._indices == [0]

    def test_parse_hardened_path(self):
        path = BIP32Path("m/44'/0'/0'")
        assert path._indices == [0x8000002C, 0x80000000, 0x80000000]

    def test_parse_full_bip44_path(self):
        path = BIP32Path("m/44'/0'/0'/0/0")
        assert len(path._indices) == 5

    def test_parse_m_only(self):
        path = BIP32Path("m")
        assert path._indices == []

    def test_invalid_path_without_m(self):
        with pytest.raises(ValueError, match="must start with 'm'"):
            BIP32Path("44'/0'/0'")


class TestExtendedKey:
    """Tests for ExtendedKey serialization and derivation."""

    def test_extended_key_from_seed(self):
        seed = bytes.fromhex(
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f"
        )
        h = hmac.new(b"Bitcoin seed", seed, __import__("hashlib").sha512)
        digest = h.digest()
        il, ir = digest[:32], digest[32:]

        ek = ExtendedKey(
            key=il,
            chain_code=ir,
            version=BIP32_VERSION_MAINNET_PRIV,
            depth=0,
            parent_fingerprint=0,
            child_index=0,
            is_private=True,
        )

        assert ek.is_private
        assert ek.depth == 0

    def test_to_base58_and_back(self):
        seed = bytes.fromhex(
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f"
        )
        h = hmac.new(b"Bitcoin seed", seed, __import__("hashlib").sha512)
        digest = h.digest()
        il, ir = digest[:32], digest[32:]

        ek = ExtendedKey(
            key=il,
            chain_code=ir,
            version=BIP32_VERSION_MAINNET_PRIV,
            depth=0,
            parent_fingerprint=0,
            child_index=0,
            is_private=True,
        )

        encoded = ek.to_base58()
        assert encoded.startswith("xprv")

        ek2 = ExtendedKey.from_base58(encoded)
        assert ek2.key == ek.key
        assert ek2.chain_code == ek.chain_code
        assert ek2.is_private
        assert ek2.depth == 0

    def test_public_key_fingerprint(self):
        seed = bytes.fromhex(
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f"
        )
        h = hmac.new(b"Bitcoin seed", seed, __import__("hashlib").sha512)
        digest = h.digest()
        il, ir = digest[:32], digest[32:]

        priv_ek = ExtendedKey(
            key=il,
            chain_code=ir,
            version=BIP32_VERSION_MAINNET_PRIV,
            depth=0,
            is_private=True,
        )

        pub_ek = ExtendedKey(
            key=priv_ek.public_key().data,
            chain_code=ir,
            version=BIP32_VERSION_MAINNET_PRIV,
            depth=0,
            is_private=False,
        )

        assert priv_ek.fingerprint == pub_ek.fingerprint


class TestBIP39Seed:
    """Tests for BIP39 mnemonic to seed derivation."""

    def test_empty_mnemonic_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            mnemonic_to_seed("")

    def test_known_vector(self):
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        seed = mnemonic_to_seed(mnemonic, "")
        expected = bytes.fromhex(
            "5eb00bbddcf069084889a8ab9155568165f5c453ccb85e70811aaed6f6da5fc19a5ac40b389cd370d086206dec8aa6c43daea6690f20ad3d8d48b2d2ce9e38e4"
        )
        assert seed == expected

    def test_known_vector_with_passphrase(self):
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        seed = mnemonic_to_seed(mnemonic, "TREZOR")
        expected = bytes.fromhex(
            "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04"
        )
        assert seed == expected


class TestHDWalletGenerate:
    """Tests for HD wallet generation."""

    def test_generate_random_wallet(self):
        wallet = HDWallet.generate(oxc_mainnet())
        assert wallet.root_key.is_private
        assert wallet.root_key.depth == 0

    def test_generate_from_known_seed(self):
        seed = bytes.fromhex(
            "000102030405060708090a0b0c0d0e0f"
            "101112131415161718191a1b1c1d1e1f"
        )
        wallet = HDWallet.generate(oxc_mainnet(), seed=seed)

        assert wallet.root_key.is_private
        assert wallet.root_key.version == BIP32_VERSION_MAINNET_PRIV


class TestHDWalletFromMnemonic:
    """Tests for HD wallet from BIP39 mnemonic."""

    def test_from_mnemonic_oxc(self):
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        wallet = HDWallet.from_mnemonic(oxc_mainnet(), mnemonic)

        assert wallet.root_key.is_private

    def test_from_mnemonic_oxg(self):
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        wallet = HDWallet.from_mnemonic(oxg_mainnet(), mnemonic)

        assert wallet.root_key.is_private

    def test_from_mnemonic_with_passphrase(self):
        mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        wallet = HDWallet.from_mnemonic(oxc_mainnet(), mnemonic, passphrase="TREZOR")

        assert wallet.root_key.is_private


class TestHDWalletDerivation:
    """Tests for HD wallet key derivation."""

    def test_derive_account_oxc(self):
        wallet = HDWallet.generate(oxc_mainnet())
        account_key = wallet.derive_account(0)

        assert account_key.depth == 3
        assert account_key.is_private

    def test_derive_account_oxg(self):
        wallet = HDWallet.generate(oxg_mainnet())
        account_key = wallet.derive_account(0)

        assert account_key.depth == 3
        assert account_key.is_private

    def test_derive_external_chain(self):
        wallet = HDWallet.generate(oxc_mainnet())
        account_key = wallet.derive_account(0)
        chain_key = wallet.derive_external_chain(account_key)

        assert chain_key.depth == 4

    def test_derive_internal_chain(self):
        wallet = HDWallet.generate(oxc_mainnet())
        account_key = wallet.derive_account(0)
        chain_key = wallet.derive_internal_chain(account_key)

        assert chain_key.depth == 4

    def test_derive_address(self):
        wallet = HDWallet.generate(oxc_mainnet())
        account_key = wallet.derive_account(0)
        external_chain = wallet.derive_external_chain(account_key)

        addr_info = wallet.derive_address(external_chain, 0)

        assert "private_key" in addr_info
        assert "public_key" in addr_info
        assert "p2pkh" in addr_info
        assert "p2wpkh" in addr_info
        assert addr_info["p2pkh"].startswith("X")

    def test_derive_address_oxg(self):
        # Use a deterministic seed for consistent address generation
        seed = bytes.fromhex("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
        wallet = HDWallet.generate(oxg_mainnet(), seed=seed)
        account_key = wallet.derive_account(0)
        external_chain = wallet.derive_external_chain(account_key)

        addr_info = wallet.derive_address(external_chain, 0)

        # Verify it's a valid OXG address (version byte 39 = 'G')
        from ordex.core.base58 import b58check_decode
        version, _ = b58check_decode(addr_info["p2pkh"])
        assert version == bytes([39])
        assert addr_info["p2wpkh"].startswith("oxg1")

    def test_get_receiving_addresses(self):
        wallet = HDWallet.generate(oxc_mainnet())
        addresses = wallet.get_receiving_addresses(0, count=5)

        assert len(addresses) == 5
        for addr in addresses:
            assert "p2pkh" in addr
            assert "p2wpkh" in addr

    def test_get_change_addresses(self):
        wallet = HDWallet.generate(oxc_mainnet())
        addresses = wallet.get_change_addresses(0, count=5)

        assert len(addresses) == 5
        for addr in addresses:
            assert "path" in addr
            assert "/1/" in addr["path"]


class TestHDWalletTestnet:
    """Tests for HD wallet on testnet."""

    def test_testnet_version(self):
        wallet = HDWallet.generate(oxc_testnet())
        assert wallet.root_key.version == BIP32_VERSION_TESTNET_PRIV

    def test_testnet_address_prefix(self):
        wallet = HDWallet.generate(oxc_testnet())
        addresses = wallet.get_receiving_addresses(0, count=1)

        assert addresses[0]["p2pkh"].startswith("m") or addresses[0]["p2pkh"].startswith("n")


class TestExtendedKeyDerivation:
    """Tests for ExtendedKey derive and derive_path methods."""

    def test_derive_normal_key(self):
        wallet = HDWallet.generate(oxc_mainnet())
        child = wallet.root_key.derive(0)

        assert child.depth == 1
        assert child.is_private

    def test_derive_hardened_key(self):
        wallet = HDWallet.generate(oxc_mainnet())
        child = wallet.root_key.derive(0, hardened=True)

        assert child.depth == 1
        assert child.is_private
        assert child.child_index & 0x80000000

    def test_derive_path_bip44(self):
        wallet = HDWallet.generate(oxc_mainnet())
        key = wallet.root_key.derive_path("m/44'/0'/0'/0/0")

        assert key.depth == 5
        assert key.is_private

    def test_derive_path_roundtrip(self):
        wallet = HDWallet.generate(oxc_mainnet())
        account = wallet.derive_account(0)
        external = wallet.derive_external_chain(account)
        addr0 = wallet.derive_address(external, 0)

        key_from_path = wallet.root_key.derive_path("m/44'/0'/0'/0/0")
        assert key_from_path.private_key().secret == addr0["private_key"].secret


class TestHDWalletFromExtendedKey:
    """Tests for HD wallet from extended key string."""

    def test_from_extended_key(self):
        wallet = HDWallet.generate(oxc_mainnet())
        xprv = wallet.root_key.to_base58()

        wallet2 = HDWallet.from_extended_key(xprv)
        assert wallet2.root_key.key == wallet.root_key.key
        assert wallet2.root_key.chain_code == wallet.root_key.chain_code