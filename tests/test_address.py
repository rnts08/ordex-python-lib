"""
Tests for address generation and Base58/Bech32 encoding.
"""

import pytest

from ordex.chain.chainparams import oxc_mainnet, oxg_mainnet
from ordex.core.base58 import b58encode, b58decode, b58check_encode, b58check_decode, bech32_encode, bech32_decode
from ordex.core.key import PrivateKey, PublicKey
from ordex.wallet.address import pubkey_to_p2pkh, pubkey_to_bech32, privkey_to_wif, generate_keypair


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
        assert "p2wpkh" in kp
        assert kp["p2pkh"][0] == "X"
        assert kp["p2wpkh"].startswith("oxc1")

    def test_generate_keypair_oxg(self):
        params = oxg_mainnet()
        kp = generate_keypair(params)
        assert kp["p2pkh"][0] == "G"
        assert kp["p2wpkh"].startswith("oxg1")
