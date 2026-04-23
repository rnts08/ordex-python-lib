"""
Tests for transaction signing.
"""

import pytest

from ordex.core.key import PrivateKey
from ordex.wallet.signing import (
    sign_transaction_input, sign_p2pkh_input, create_signed_transaction,
    SIGHASH_ALL, SIGHASH_NONE, SIGHASH_SINGLE, SIGHASH_ANYONECANPAY,
)
from ordex.primitives.transaction import CTransaction, CTxIn, CTxOut, COutPoint
from ordex.core.script import CScript


class TestTransactionSigning:
    """Tests for transaction signing functionality."""

    def test_create_signed_transaction(self):
        """Test creating and signing a basic P2PKH transaction."""
        privkey = PrivateKey.generate()
        
        inputs = [
            ('0000000000000000000000000000000000000000000000000000000000000000', 0, 100000000),
        ]
        outputs = [
            ('Xu9T6ni9x176RBLFKGErYDpWr7HceVocjQ', 50000000),
        ]
        
        tx = create_signed_transaction(inputs, outputs, privkey)
        
        assert tx.version == 2
        assert len(tx.vin) == 1
        assert len(tx.vout) == 1
        assert tx.vout[0].value == 50000000
        assert len(tx.vin[0].script_sig) > 0

    def test_transaction_has_valid_txid(self):
        """Test that signed transaction has a valid txid."""
        privkey = PrivateKey.generate()
        
        inputs = [
            ('0000000000000000000000000000000000000000000000000000000000000000', 0, 100000000),
        ]
        outputs = [
            ('Xu9T6ni9x176RBLFKGErYDpWr7HceVocjQ', 50000000),
        ]
        
        tx = create_signed_transaction(inputs, outputs, privkey)
        
        # txid should be 32 bytes
        assert len(tx.txid()) == 32

    def test_sign_p2pkh_input(self):
        """Test signing a single P2PKH input."""
        privkey = PrivateKey.generate()
        
        # Create a basic transaction
        tx = CTransaction(
            version=1,
            vin=[
                CTxIn(
                    prevout=COutPoint(b'\x00' * 32, 0),
                    sequence=0xFFFFFFFF,
                )
            ],
            vout=[
                CTxOut(value=50000000, script_pubkey=CScript.p2pkh(privkey.public_key().hash160()))
            ],
            locktime=0,
        )
        
        sign_p2pkh_input(tx, 0, privkey)
        
        assert len(tx.vin[0].script_sig) > 0

    def test_sign_multiple_inputs(self):
        """Test signing a transaction with multiple inputs."""
        privkey = PrivateKey.generate()
        
        inputs = [
            ('0000000000000000000000000000000000000000000000000000000000000000', 0, 50000000),
            ('1111111111111111111111111111111111111111111111111111111111111111', 0, 50000000),
        ]
        outputs = [
            ('Xu9T6ni9x176RBLFKGErYDpWr7HceVocjQ', 80000000),
        ]
        
        tx = create_signed_transaction(inputs, outputs, privkey)
        
        assert len(tx.vin) == 2
        assert len(tx.vin[0].script_sig) > 0
        assert len(tx.vin[1].script_sig) > 0

    def test_sighash_constants(self):
        """Test that sighash constants are defined correctly."""
        assert SIGHASH_ALL == 1
        assert SIGHASH_NONE == 2
        assert SIGHASH_SINGLE == 3
        assert SIGHASH_ANYONECANPAY == 0x80

    def test_coinbase_not_signed(self):
        """Test that coinbase inputs are not signed."""
        privkey = PrivateKey.generate()
        
        tx = CTransaction(
            version=1,
            vin=[
                CTxIn(
                    prevout=COutPoint(b'\xff' * 32, 0xFFFFFFFF),  # Coinbase prevout
                    sequence=0xFFFFFFFF,
                )
            ],
            vout=[
                CTxOut(value=100000000, script_pubkey=b'')
            ],
            locktime=0,
        )
        
        # Should not raise - coinbase is skipped
        sign_p2pkh_input(tx, 0, privkey, is_coinbase=True)
        
        # script_sig should still be empty for coinbase
        assert tx.vin[0].script_sig == b''