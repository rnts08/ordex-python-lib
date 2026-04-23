"""
BIP32 HD Wallet implementation for OrdexCoin and OrdexGold.

Provides hierarchical deterministic key derivation as per BIP32.
"""

from __future__ import annotations

import hmac
import hashlib
import struct
from typing import Optional, Tuple

from ordex.core.key import PrivateKey, PublicKey
from ordex.core.hash import hash160, sha256d


BIP32_VERSION_MAINNET_PUB = 0x0488B21E  # Extended key version for mainnet (public)
BIP32_VERSION_MAINNET_PRIV = 0x0488ADE4  # Extended key version for mainnet (private)
BIP32_VERSION_TESTNET_PUB = 0x043587CF  # Extended key version for testnet (public)
BIP32_VERSION_TESTNET_PRIV = 0x04358395  # Extended key version for testnet (private)


def _get_version(version: int, is_private: bool, network_id: str) -> int:
    """Get the correct version byte based on key type and network."""
    if is_private:
        return BIP32_VERSION_MAINNET_PRIV if network_id == "main" else BIP32_VERSION_TESTNET_PRIV
    else:
        return BIP32_VERSION_MAINNET_PUB if network_id == "main" else BIP32_VERSION_TESTNET_PUB


from ecdsa import SECP256k1

SECP256K1_ORDER = SECP256k1.order


class BIP32Path:
    """Represents a BIP32 derivation path."""
    
    def __init__(self, path: str = "m") -> None:
        self.path = path
        self._indices = self._parse(path)
    
    def _parse(self, path: str) -> list:
        """Parse a derivation path like m/44'/0'/0'/0/0"""
        if not path.startswith("m"):
            raise ValueError("Path must start with 'm'")
        
        parts = path.split("/")
        indices = []
        
        for part in parts[1:]:  # Skip 'm'
            if part.endswith("'"):
                hardened = True
                index = int(part[:-1])
            else:
                hardened = False
                index = int(part)
            
            if hardened:
                index |= 0x80000000  # Add hardened flag
            
            indices.append(index)
        
        return indices
    
    def __str__(self) -> str:
        return self.path
    
    def __repr__(self) -> str:
        return f"BIP32Path('{self.path}')"


class ExtendedKey:
    """An extended key (private or public) for BIP32."""
    
    def __init__(
        self,
        key: bytes,
        chain_code: bytes,
        version: int,
        depth: int = 0,
        parent_fingerprint: int = 0,
        child_index: int = 0,
        is_private: bool = True,
    ) -> None:
        self.key = key  # 32 bytes for private, 33 for public
        self.chain_code = chain_code  # 32 bytes
        self.version = version
        self.depth = depth
        self.parent_fingerprint = parent_fingerprint
        self.child_index = child_index
        self.is_private = is_private
    
    @property
    def fingerprint(self) -> int:
        """Get the fingerprint of this key."""
        if self.is_private:
            # For private keys, derive the public key first
            priv = PrivateKey(self.key)
            pub = priv.public_key(compressed=True)
            hash160_bytes = hash160(pub.data)
        else:
            hash160_bytes = hash160(self.key)
        return int.from_bytes(hash160_bytes[:4], "big")
    
    def to_base58(self) -> str:
        """Serialize the extended key to Base58Check format."""
        from ordex.core.base58 import b58check_encode, b58encode, sha256d
        
        # Determine correct version based on key type
        version = self.version
        if self.is_private:
            if version == BIP32_VERSION_MAINNET_PUB:
                version = BIP32_VERSION_MAINNET_PRIV
            elif version == BIP32_VERSION_TESTNET_PUB:
                version = BIP32_VERSION_TESTNET_PRIV
        else:
            if version == BIP32_VERSION_MAINNET_PRIV:
                version = BIP32_VERSION_MAINNET_PUB
            elif version == BIP32_VERSION_TESTNET_PRIV:
                version = BIP32_VERSION_TESTNET_PUB
        
        # Format: version (4) + depth (1) + parent_fp (4) + child_idx (4) + chain_code (32) + key (33/32)
        data = b""
        data += struct.pack(">I", version)
        data += struct.pack("B", self.depth)
        data += struct.pack(">I", self.parent_fingerprint)
        data += struct.pack(">I", self.child_index)
        data += self.chain_code
        
        if self.is_private:
            data += b"\x00" + self.key  # 0x00 prefix for private keys
        else:
            data += self.key
        
        # Extended key uses version as first 4 bytes, not 1 byte
        # So we do base58check manually: version (4) + payload + checksum
        checksum = sha256d(data)[:4]
        return b58encode(data + checksum)
    
    @classmethod
    def from_base58(cls, encoded: str) -> "ExtendedKey":
        """Deserialize an extended key from Base58Check format."""
        from ordex.core.base58 import b58decode, b58encode, sha256d
        
        data = b58decode(encoded)
        
        # Verify checksum
        payload, checksum = data[:-4], data[-4:]
        if sha256d(payload)[:4] != checksum:
            raise ValueError("Invalid checksum")
        
        # Format: version (4) + depth (1) + parent_fp (4) + child_idx (4) + chain_code (32) + key (33/32)
        if len(payload) != 78:
            raise ValueError(f"Invalid extended key length: {len(payload)}")
        
        version_int = struct.unpack(">I", payload[:4])[0]
        depth = payload[4]
        parent_fp = struct.unpack(">I", payload[5:9])[0]
        child_idx = struct.unpack(">I", payload[9:13])[0]
        chain_code = payload[13:45]
        key = payload[45:]
        
        is_private = key[0] == 0
        if is_private:
            key = key[1:]  # Remove 0x00 prefix
        
        return cls(
            key=key,
            chain_code=chain_code,
            version=version_int,
            depth=depth,
            parent_fingerprint=parent_fp,
            child_index=child_idx,
            is_private=is_private,
        )
    
    def derive(self, index: int, hardened: bool = False) -> "ExtendedKey":
        """Derive a child key at the given index.
        
        Args:
            index: Child index (0-2^31-1 for normal, 2^31-2^32-1 for hardened)
            hardened: Whether to use hardened derivation
            
        Returns:
            New ExtendedKey instance
        """
        if hardened:
            index |= 0x80000000  # Set hardened bit
        
        if self.is_private:
            # Private key derivation
            if hardened:
                # Hardened: 0x00 || ser256(k) || ser32(i)
                data = b"\x00" + self.key + struct.pack(">I", index)
            else:
                # Normal: serP(point(k)) || ser32(i)
                priv = PrivateKey(self.key)
                pub = priv.public_key(compressed=True)
                data = pub.data + struct.pack(">I", index)
        else:
            # Public key derivation
            data = self.key + struct.pack(">I", index)
        
        # HMAC-SHA512 with chain code as key
        h = hmac.new(self.chain_code, data, hashlib.sha512)
        digest = h.digest()
        il, ir = digest[:32], digest[32:]
        
        il_int = int.from_bytes(il, "big")
        
        if self.is_private:
            # Child private key = parse256(il) + k (mod n)
            child_key = (il_int + int.from_bytes(self.key, "big")) % SECP256K1_ORDER
            child_key = child_key.to_bytes(32, "big")
            
            return ExtendedKey(
                key=child_key,
                chain_code=ir,
                version=self.version,
                depth=self.depth + 1,
                parent_fingerprint=self.fingerprint,
                child_index=index,
                is_private=True,
            )
        else:
            # Child public key = point(il) + parent_pubkey
            # For simplicity, we use the ecdsa library
            from ecdsa import SECP256k1, ellipticcurve
            
            # Get parent public key point
            priv = PrivateKey(self.key)
            vk = priv._key.get_verifying_key()
            parent_point = vk.pubkey.point
            
            # Multiply il by G
            il_point = SECP256k1.generator * il_int
            
            # Add to parent point
            child_x = (parent_point.x() + il_point.x()) % SECP256k1.curve.p
            child_y = (parent_point.y() + il_point.y()) % SECP256k1.curve.p
            
            child_key = PublicKey.from_point(child_x, child_y, compressed=True).data
            
            return ExtendedKey(
                key=child_key,
                chain_code=ir,
                version=self.version,
                depth=self.depth + 1,
                parent_fingerprint=self.fingerprint,
                child_index=index,
                is_private=False,
            )
    
    def derive_path(self, path: str) -> "ExtendedKey":
        """Derive a key from a path like m/44'/0'/0'/0/0"""
        bip32_path = BIP32Path(path)
        key = self
        
        for idx in bip32_path._indices:
            hardened = bool(idx & 0x80000000)
            index = idx & 0x7FFFFFFF
            key = key.derive(index, hardened)
        
        return key
    
    def private_key(self) -> PrivateKey:
        """Get the PrivateKey object from this extended key."""
        if not self.is_private:
            raise ValueError("Cannot get private key from public extended key")
        return PrivateKey(self.key)
    
    def public_key(self) -> PublicKey:
        """Get the PublicKey object from this extended key."""
        if self.is_private:
            return PrivateKey(self.key).public_key(compressed=True)
        return PublicKey(self.key)
    
    def __repr__(self) -> str:
        return f"ExtendedKey(depth={self.depth}, is_private={self.is_private}, fingerprint={self.fingerprint:08x})"


class HDWallet:
    """HD Wallet for BIP32 key derivation."""
    
    def __init__(self, root_key: ExtendedKey, params) -> None:
        self.root_key = root_key
        self.params = params
    
    @classmethod
    def generate(cls, params, seed: Optional[bytes] = None) -> "HDWallet":
        """Generate a new HD wallet from random seed or specified seed.
        
        Args:
            params: ChainParams for the network
            seed: Optional 64-byte seed (if None, generates random)
            
        Returns:
            HDWallet instance
        """
        if seed is None:
            import os
            seed = os.urandom(64)
        
        # BIP32 seed derivation using "Bitcoin seed"
        h = hmac.new(b"Bitcoin seed", seed, hashlib.sha512)
        digest = h.digest()
        il, ir = digest[:32], digest[32:]
        
        version = BIP32_VERSION_MAINNET_PRIV if params.network_id == "main" else BIP32_VERSION_TESTNET_PRIV
        
        root_key = ExtendedKey(
            key=il,
            chain_code=ir,
            version=version,
            depth=0,
            parent_fingerprint=0,
            child_index=0,
            is_private=True,
        )
        
        return cls(root_key, params)
    
    @classmethod
    def from_mnemonic(cls, params, mnemonic: str, passphrase: str = "") -> "HDWallet":
        """Create HD wallet from BIP39 mnemonic.
        
        Args:
            params: ChainParams for the network
            mnemonic: BIP39 mnemonic phrase
            passphrase: Optional passphrase for PBKDF2
            
        Returns:
            HDWallet instance
        """
        from .bip39 import mnemonic_to_seed
        seed = mnemonic_to_seed(mnemonic, passphrase)
        return cls.generate(params, seed)
    
    @classmethod
    def from_extended_key(cls, extended_key: str) -> "HDWallet":
        """Create HD wallet from an extended key string.
        
        Args:
            extended_key: Base58 encoded extended private key
            
        Returns:
            HDWallet instance
        """
        key = ExtendedKey.from_base58(extended_key)
        
        # Determine params from version
        if key.version in (BIP32_VERSION_MAINNET_PUB, BIP32_VERSION_MAINNET_PRIV):
            from ordex.chain.chainparams import oxc_mainnet
            params = oxc_mainnet()
        else:
            from ordex.chain.chainparams import oxc_testnet
            params = oxc_testnet()
        
        return cls(key, params)
    
    def derive_account(self, account: int, purpose: int = 44) -> ExtendedKey:
        """Derive an account key (e.g., m/44'/0'/0').
        
        For OrdexCoin (OXC): purpose=44, coin_type=0
        For OrdexGold (OXG): purpose=44, coin_type=1
        
        Args:
            account: Account index
            purpose: BIP purpose (default: 44 for BIP44)
            
        Returns:
            ExtendedKey for the account
        """
        # Determine coin type from params
        if self.params.pubkey_address_prefix == bytes([76]):  # OXC mainnet
            coin_type = 0
        elif self.params.pubkey_address_prefix == bytes([39]):  # OXG mainnet
            coin_type = 1
        else:  # Testnet
            coin_type = 1  # Use same as OXG testnet
        
        # Derive: m/purpose'/coin'/account'
        path = f"m/{purpose}'/{coin_type}'/{account}'"
        return self.root_key.derive_path(path)
    
    def derive_external_chain(self, account_key: ExtendedKey) -> ExtendedKey:
        """Derive the external chain (receive addresses).
        
        Args:
            account_key: Account extended key
            
        Returns:
            ExtendedKey for external chain
        """
        return account_key.derive(0)
    
    def derive_internal_chain(self, account_key: ExtendedKey) -> ExtendedKey:
        """Derive the internal chain (change addresses).
        
        Args:
            account_key: Account extended key
            
        Returns:
            ExtendedKey for internal chain
        """
        return account_key.derive(1)
    
    def derive_address(self, chain_key: ExtendedKey, index: int) -> dict:
        """Derive an address at the given index.
        
        Args:
            chain_key: Chain extended key (external or internal)
            index: Address index
            
        Returns:
            Dict with privkey, pubkey, address info
        """
        key = chain_key.derive(index)
        
        from ordex.wallet.address import (
            pubkey_to_p2pkh, pubkey_to_bech32, privkey_to_wif,
            generate_keypair,
        )
        
        pubkey = key.public_key()
        privkey = key.private_key() if key.is_private else None
        
        return {
            "private_key": privkey,
            "public_key": pubkey,
            "pubkey_hash": pubkey.hash160(),
            "p2pkh": pubkey_to_p2pkh(pubkey, self.params),
            "p2wpkh": pubkey_to_bech32(pubkey, self.params),
            "wif": privkey_to_wif(privkey, self.params) if privkey else None,
            "path": f"m/44'/{1 if self.params.pubkey_address_prefix == bytes([39]) else 0}'/0'/{0 if chain_key.child_index == 0 else 1}/{index}",
        }
    
    def get_receiving_addresses(self, account: int = 0, count: int = 20) -> list:
        """Get a list of receiving addresses.
        
        Args:
            account: Account index
            count: Number of addresses to generate
            
        Returns:
            List of address dicts
        """
        account_key = self.derive_account(account)
        external_chain = self.derive_external_chain(account_key)
        
        return [self.derive_address(external_chain, i) for i in range(count)]
    
    def get_change_addresses(self, account: int = 0, count: int = 20) -> list:
        """Get a list of change addresses.
        
        Args:
            account: Account index
            count: Number of addresses to generate
            
        Returns:
            List of address dicts
        """
        account_key = self.derive_account(account)
        internal_chain = self.derive_internal_chain(account_key)
        
        return [self.derive_address(internal_chain, i) for i in range(count)]