"""
Transaction signing for OrdexCoin and OrdexGold.

Provides transaction signing functionality using ECDSA.
"""

from __future__ import annotations

from typing import List, Optional

from ordex.core.key import PrivateKey, PublicKey
from ordex.core.script import CScript, OP_CHECKSIG
from ordex.primitives.transaction import CTransaction, CTxIn, CTxOut, COutPoint


SIGHASH_ALL = 1
SIGHASH_NONE = 2
SIGHASH_SINGLE = 3
SIGHASH_ANYONECANPAY = 0x80


class TransactionSignature:
    """Represents a transaction input signature."""

    def __init__(self, signature: bytes, sighash_type: int = SIGHASH_ALL) -> None:
        self.signature = signature
        self.sighash_type = sighash_type

    def bytes(self) -> bytes:
        """Return signature with sighash type appended."""
        return self.signature + bytes([self.sighash_type])


def _sighash_prepare_transaction(
    tx: CTransaction,
    input_index: int,
    script_code: bytes,
    sighash_type: int,
) -> bytes:
    """Create the transaction preimage for signing.
    
    This implements the Bitcoin Core signature hash algorithm.
    """
    import struct
    from io import BytesIO
    
    # Version
    result = struct.pack("<i", tx.version)
    
    # Inputs
    if sighash_type & SIGHASH_ANYONECANPAY != SIGHASH_ANYONECANPAY:
        result += struct.pack("<I", len(tx.vin))
        for i, txin in enumerate(tx.vin):
            if i == input_index:
                # Serialize prevout
                buf = BytesIO()
                txin.prevout.serialize(buf)
                result += buf.getvalue()
                result += script_code
                result += struct.pack("<I", txin.sequence)
            else:
                buf = BytesIO()
                txin.prevout.serialize(buf)
                result += buf.getvalue()
                result += b""
                result += struct.pack("<I", 0 if (sighash_type & SIGHASH_ANYONECANPAY) else txin.sequence)
    
    # Outputs
    if sighash_type & 0x1f == SIGHASH_NONE:
        result += struct.pack("<I", 0)
    elif sighash_type & 0x1f == SIGHASH_SINGLE:
        result += struct.pack("<I", input_index + 1)
        for i, txout in enumerate(tx.vout):
            if i == input_index:
                result += txout.value.to_bytes(8, "little", signed=True)
                result += bytes([len(txout.script_pubkey)]) + txout.script_pubkey
            else:
                result += (0).to_bytes(8, "little", signed=True)
                result += bytes([0])
    else:
        result += struct.pack("<I", len(tx.vout))
        for txout in tx.vout:
            result += txout.value.to_bytes(8, "little", signed=True)
            result += bytes([len(txout.script_pubkey)]) + txout.script_pubkey
    
    # Locktime
    result += struct.pack("<I", tx.locktime)
    
    # Sighash type
    result += struct.pack("<I", sighash_type)
    
    return result


def sign_transaction_input(
    tx: CTransaction,
    input_index: int,
    private_key: PrivateKey,
    script_code: bytes,
    sighash_type: int = SIGHASH_ALL,
) -> bytes:
    """Sign a single transaction input.
    
    Args:
        tx: The transaction to sign
        input_index: Index of the input to sign
        private_key: The private key to sign with
        script_code: The script being spent (for P2PKH: OP_DUP OP_HASH160 <pubkeyhash> OP_EQUALVERIFY OP_CHECKSIG)
        sighash_type: Signature hash type (default: SIGHASH_ALL)
    
    Returns:
        The signature bytes with sighash type appended.
    """
    # Create preimage
    preimage = _sighash_prepare_transaction(tx, input_index, script_code, sighash_type)
    
    # Hash the preimage (double SHA-256)
    from ordex.core.hash import sha256d
    hash_to_sign = sha256d(preimage)
    
    # Sign
    signature = private_key.sign(hash_to_sign)
    
    return signature + bytes([sighash_type])


def sign_p2pkh_input(
    tx: CTransaction,
    input_index: int,
    private_key: PrivateKey,
    is_coinbase: bool = False,
) -> None:
    """Sign a P2PKH input and update the transaction.
    
    Args:
        tx: The transaction to sign (modified in place)
        input_index: Index of the input to sign
        private_key: The private key to sign with
        is_coinbase: Whether this is a coinbase input (skip signing)
    """
    if is_coinbase:
        return
    
    pubkey = private_key.public_key(compressed=True)
    pubkey_hash = pubkey.hash160()
    
    # Create the script code (P2PKH script)
    script_code = CScript.p2pkh(pubkey_hash)
    
    # Sign
    signature_with_type = sign_transaction_input(
        tx, input_index, private_key, bytes(script_code), SIGHASH_ALL
    )
    
    # Build the scriptSig: [signature] [pubkey]
    script_sig = CScript.from_ops(
        signature_with_type,
        pubkey.data,
    )
    
    tx.vin[input_index].script_sig = script_sig


def create_signed_transaction(
    inputs: List[tuple],
    outputs: List[tuple],
    private_key: PrivateKey,
    version: int = 2,
    locktime: int = 0,
) -> CTransaction:
    """Create and sign a basic P2PKH transaction.
    
    Args:
        inputs: List of (txid, vout, amount) tuples for inputs
        outputs: List of (address, amount) tuples for outputs
        private_key: The key to sign with
        version: Transaction version
        locktime: Locktime
    
    Returns:
        Signed CTransaction
    """
    from ordex.wallet.address import p2pkh_to_pubkey_hash
    
    vin = []
    for txid, vout, amount in inputs:
        # Decode address to get pubkey hash for script
        prevout = COutPoint(bytes.fromhex(txid)[::-1], vout)
        vin.append(CTxIn(prevout=prevout, sequence=0xFFFFFFFF))
    
    vout = []
    pubkey = private_key.public_key(compressed=True)
    for address, amount in outputs:
        # For now, assume P2PKH output
        try:
            version_byte, pkh = p2pkh_to_pubkey_hash(address)
            script_pubkey = CScript.p2pkh(pkh)
        except ValueError:
            # Try bech32
            from ordex.wallet.address import bech32_to_pubkey_hash
            hrp, witver, witprog = bech32_to_pubkey_hash(address)
            script_pubkey = CScript.p2wpkh(witprog)
        
        vout.append(CTxOut(value=amount, script_pubkey=script_pubkey))
    
    tx = CTransaction(
        version=version,
        vin=vin,
        vout=vout,
        locktime=locktime,
    )
    
    # Sign each input
    for i in range(len(tx.vin)):
        sign_p2pkh_input(tx, i, private_key)
    
    return tx