"""
Tests for address generation and Base58/Bech32 encoding.
"""

import pytest

from ordex.chain.chainparams import oxc_mainnet, oxg_mainnet
from ordex.core.base58 import b58encode, b58decode, b58check_encode, b58check_decode, bech32_encode, bech32_decode
from ordex.core.key import PrivateKey, PublicKey
from ordex.wallet.address import (
    pubkey_to_p2pkh, pubkey_to_bech32, privkey_to_wif, generate_keypair,
    p2pkh_to_pubkey_hash, bech32_to_pubkey_hash, decode_address,
    script_to_p2sh, p2sh_to_script_hash,
)
from ordex.core.script import CScript


class TestBase58:
    def test_encode_decode_roundtrip(self):
        data = b"\x00\x01\x02\x03\x04"
        encoded = b58encode(data)
        decoded = b58decode(encoded)
        assert decoded == data

    def test_leading_zeros(self):
        data = b"\x00\x00\x00\x01"
        encoded = b58encode(data)
        assert encoded.startswith("111")
        decoded = b58decode(encoded)
        assert decoded == data

    def test_check_encode_decode(self):
        version = b"\x00"
        payload = b"\xab" * 20
        encoded = b58check_encode(version, payload)
        dec_ver, dec_payload = b58check_decode(encoded)
        assert dec_ver == version
        assert dec_payload == payload

    def test_check_decode_bad_checksum(self):
        version = b"\x00"
        payload = b"\xab" * 20
        encoded = b58check_encode(version, payload)
        # Corrupt the last character
        corrupted = encoded[:-1] + ("1" if encoded[-1] != "1" else "2")
        with pytest.raises(ValueError, match="checksum"):
            b58check_decode(corrupted)


class TestBech32:
    def test_encode_decode_roundtrip(self):
        hrp = "oxc"
        witver = 0
        witprog = b"\xab" * 20
        encoded = bech32_encode(hrp, witver, witprog)
        assert encoded.startswith("oxc1")

        dec_hrp, dec_ver, dec_prog = bech32_decode(encoded)
        assert dec_hrp == hrp
        assert dec_ver == witver
        assert dec_prog == witprog

    def test_oxg_hrp(self):
        encoded = bech32_encode("oxg", 0, b"\x00" * 20)
        assert encoded.startswith("oxg1")


class TestKeyGeneration:
    def test_private_key_length(self):
        pk = PrivateKey.generate()
        assert len(pk.secret) == 32

    def test_public_key_compressed(self):
        pk = PrivateKey.generate()
        pub = pk.public_key(compressed=True)
        assert pub.is_compressed
        assert len(pub.data) == 33

    def test_public_key_uncompressed(self):
        pk = PrivateKey.generate()
        pub = pk.public_key(compressed=False)
        assert not pub.is_compressed
        assert len(pub.data) == 65

    def test_wif_roundtrip(self):
        pk = PrivateKey.generate()
        wif = pk.to_wif(secret_key_prefix=203)  # OXC mainnet
        pk2 = PrivateKey.from_wif(wif)
        assert pk.secret == pk2.secret


class TestAddressGeneration:
    def test_oxc_p2pkh_prefix(self):
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        addr = pubkey_to_p2pkh(pub, params)
        # OXC mainnet P2PKH starts with 'X' (version 76)
        assert addr[0] == "X"

    def test_oxg_p2pkh_prefix(self):
        params = oxg_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        addr = pubkey_to_p2pkh(pub, params)
        # OXG mainnet P2PKH uses version 39 (0x27)
        # Verify by decoding - should match params.pubkey_address_prefix
        from ordex.core.base58 import b58check_decode
        ver, payload = b58check_decode(addr)
        assert ver == bytes([39])

    def test_oxc_bech32_prefix(self):
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        addr = pubkey_to_bech32(pub, params)
        assert addr.startswith("oxc1")

    def test_oxg_bech32_prefix(self):
        params = oxg_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        addr = pubkey_to_bech32(pub, params)
        assert addr.startswith("oxg1")

    def test_generate_keypair_oxc(self):
        params = oxc_mainnet()
        kp = generate_keypair(params)
        assert "privkey" in kp
        assert "pubkey" in kp
        assert "wif" in kp
        assert "p2pkh" in kp
        assert "p2sh" in kp
        assert "p2wpkh" in kp
        assert kp["p2pkh"][0] == "X"
        assert kp["p2wpkh"].startswith("oxc1")
        # Verify P2SH address
        ver, payload = b58check_decode(kp["p2sh"])
        assert ver == bytes([75])  # OXC script address prefix

    def test_generate_keypair_oxg(self):
        params = oxg_mainnet()
        kp = generate_keypair(params)
        # Verify version byte is correct (39 for OXG mainnet)
        from ordex.core.base58 import b58check_decode
        ver, payload = b58check_decode(kp["p2pkh"])
        assert ver == bytes([39])
        assert kp["p2wpkh"].startswith("oxg1")
        # Verify P2SH address
        ver, payload = b58check_decode(kp["p2sh"])
        assert ver == bytes([5])  # OXG script address prefix


class TestAddressDecoding:
    """Tests for address decoding functionality."""

    def test_p2pkh_decode_oxc(self):
        """Test decoding OXC P2PKH address."""
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        addr = pubkey_to_p2pkh(pub, params)
        version, pkh = p2pkh_to_pubkey_hash(addr)
        
        assert version == bytes([76])
        assert len(pkh) == 20
        assert pkh == pub.hash160()

    def test_p2pkh_decode_oxg(self):
        """Test decoding OXG P2PKH address."""
        params = oxg_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        addr = pubkey_to_p2pkh(pub, params)
        version, pkh = p2pkh_to_pubkey_hash(addr)
        
        assert version == bytes([39])
        assert len(pkh) == 20
        assert pkh == pub.hash160()

    def test_bech32_decode_oxc(self):
        """Test decoding OXC Bech32 address."""
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        addr = pubkey_to_bech32(pub, params)
        hrp, witver, witprog = bech32_to_pubkey_hash(addr)
        
        assert hrp == "oxc"
        assert witver == 0
        assert len(witprog) == 20
        assert witprog == pub.hash160()

    def test_bech32_decode_oxg(self):
        """Test decoding OXG Bech32 address."""
        params = oxg_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        addr = pubkey_to_bech32(pub, params)
        hrp, witver, witprog = bech32_to_pubkey_hash(addr)
        
        assert hrp == "oxg"
        assert witver == 0
        assert len(witprog) == 20
        assert witprog == pub.hash160()

    def test_decode_address_p2pkh(self):
        """Test generic decode_address for P2PKH."""
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        addr = pubkey_to_p2pkh(pub, params)
        
        result = decode_address(addr)
        assert result["type"] == "p2pkh"
        assert result["version"] == bytes([76])
        assert result["hash"] == pub.hash160()

    def test_decode_address_bech32(self):
        """Test generic decode_address for Bech32."""
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        addr = pubkey_to_bech32(pub, params)
        
        result = decode_address(addr)
        assert result["type"] == "bech32"
        assert result["hrp"] == "oxc"
        assert result["witness_version"] == 0
        assert result["hash"] == pub.hash160()

    def test_address_roundtrip_p2pkh(self):
        """Test that encoding then decoding returns original hash."""
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        # Encode
        addr = pubkey_to_p2pkh(pub, params)
        # Decode
        version, pkh = p2pkh_to_pubkey_hash(addr)
        # Verify
        assert pkh == pub.hash160()

    def test_address_roundtrip_bech32(self):
        """Test that encoding then decoding returns original hash."""
        params = oxg_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        # Encode
        addr = pubkey_to_bech32(pub, params)
        # Decode
        hrp, witver, witprog = bech32_to_pubkey_hash(addr)
        # Verify
        assert witprog == pub.hash160()

    def test_p2sh_roundtrip(self):
        """Test P2SH address encoding and decoding."""
        params = oxc_mainnet()
        pk = PrivateKey.generate()
        pub = pk.public_key()
        
        # Create P2PKH script and wrap in P2SH
        p2pkh_script = CScript.p2pkh(pub.hash160())
        p2sh_addr = script_to_p2sh(p2pkh_script, params)
        
        # Decode and verify
        version, script_hash = p2sh_to_script_hash(p2sh_addr)
        assert version == bytes([75])  # OXC script prefix
        assert len(script_hash) == 20
        
    def test_generate_keypair_p2sh_decode(self):
        """Test that generated P2SH addresses can be decoded correctly."""
        params = oxc_mainnet()
        kp = generate_keypair(params)
        
        # The P2SH is a hash of the P2PKH script
        version, script_hash = p2sh_to_script_hash(kp["p2sh"])
        
        # Verify version matches
        assert version == params.script_address_prefix
        # Verify it's a 20-byte hash
        assert len(script_hash) == 20
