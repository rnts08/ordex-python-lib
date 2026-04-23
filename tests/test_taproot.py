"""
Tests for Taproot (P2TR) address support.
"""

import pytest

from ordex.chain.chainparams import oxc_mainnet, oxg_mainnet
from ordex.core.key import PrivateKey
from ordex.wallet.address import (
    pubkey_to_p2tr, p2tr_to_pubkey_hash, generate_keypair, decode_address,
    pubkey_to_bech32,
)


class TestTaprootAddress:
    """Tests for Taproot (P2TR) address generation."""

    def test_pubkey_to_p2tr_oxc(self):
        """Test P2TR address generation for OXC."""
        params = oxc_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=True)

        p2tr_addr = pubkey_to_p2tr(pubkey, params)

        assert p2tr_addr.startswith("oxc1")
        assert len(p2tr_addr) > 20

    def test_pubkey_to_p2tr_oxg(self):
        """Test P2TR address generation for OXG."""
        params = oxg_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=True)

        p2tr_addr = pubkey_to_p2tr(pubkey, params)

        assert p2tr_addr.startswith("oxg1")

    def test_p2tr_roundtrip(self):
        """Test P2TR encode/decode roundtrip."""
        params = oxc_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=True)

        p2tr_addr = pubkey_to_p2tr(pubkey, params)
        hrp, witprog = p2tr_to_pubkey_hash(p2tr_addr)

        assert hrp == "oxc"
        assert len(witprog) == 32

    def test_p2tr_to_pubkey_hash_invalid_version(self):
        """Test that P2TR decoding rejects non-version-1 addresses."""
        params = oxc_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=True)

        p2wpkh_addr = pubkey_to_bech32(pubkey, params)
        
        # This should fail because it's version 0, not version 1
        with pytest.raises(ValueError, match="version 1"):
            p2tr_to_pubkey_hash(p2wpkh_addr)


class TestGenerateKeypairWithTaproot:
    """Tests for generate_keypair with P2TR."""

    def test_generate_keypair_includes_p2tr(self):
        """Test that generate_keypair includes P2TR address."""
        params = oxc_mainnet()
        kp = generate_keypair(params)

        assert "p2tr" in kp
        assert kp["p2tr"].startswith("oxc1")

    def test_generate_keypair_oxg_includes_p2tr(self):
        """Test that OXG generate_keypair includes P2TR."""
        params = oxg_mainnet()
        kp = generate_keypair(params)

        assert "p2tr" in kp
        assert kp["p2tr"].startswith("oxg1")


class TestDecodeAddressP2TR:
    """Tests for decode_address with P2TR."""

    def test_decode_p2tr_address(self):
        """Test decoding a P2TR address."""
        params = oxc_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=True)

        p2tr_addr = pubkey_to_p2tr(pubkey, params)
        result = decode_address(p2tr_addr)

        assert result["type"] == "p2tr"
        assert result["witness_version"] == 1
        assert len(result["hash"]) == 32

    def test_decode_p2wpkh_vs_p2tr(self):
        """Test that P2WPKH and P2TR are distinguished."""
        params = oxc_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=True)

        p2wpkh = pubkey_to_bech32(pubkey, params)
        p2tr = pubkey_to_p2tr(pubkey, params)

        result_wpkh = decode_address(p2wpkh)
        result_tr = decode_address(p2tr)

        assert result_wpkh["type"] == "p2wpkh"
        assert result_wpkh["witness_version"] == 0
        
        assert result_tr["type"] == "p2tr"
        assert result_tr["witness_version"] == 1


class TestTaprootUncompressed:
    """Tests for Taproot with uncompressed keys."""

    def test_uncompressed_pubkey_to_p2tr(self):
        """Test P2TR with uncompressed public key."""
        params = oxc_mainnet()
        privkey = PrivateKey.generate()
        pubkey = privkey.public_key(compressed=False)

        p2tr_addr = pubkey_to_p2tr(pubkey, params)

        assert p2tr_addr.startswith("oxc1")