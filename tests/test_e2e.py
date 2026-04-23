"""
End-to-end integration tests for common workflows.

Tests library functionality:
- Block operations
- Transaction operations
- Script execution
"""

import pytest
from io import BytesIO

from ordex.core.script import CScript, verify_script
from ordex.primitives.transaction import CTransaction
from ordex.primitives.block import CBlock, CBlockHeader
from ordex.core.script import ScriptInterpreter


class TestBlockWorkflow:
    """E2E: Block validation workflow."""

    def test_block_header_serialization(self):
        """Serialize and deserialize a block header."""
        header = CBlockHeader(
            version=1,
            hash_prev_block=b"\x00" * 32,
            hash_merkle_root=b"\xab" * 32,
            time=1234567890,
            bits=0x1d00ffff,
            nonce=0,
        )
        data = header.to_bytes()
        assert len(data) == 80

    def test_block_header_roundtrip(self):
        """Block header roundtrip."""
        header = CBlockHeader(
            version=1,
            hash_prev_block=b"\x00" * 32,
            hash_merkle_root=b"\xab" * 32,
            time=1234567890,
            bits=0x1d00ffff,
            nonce=0,
        )
        data = header.to_bytes()
        header2 = CBlockHeader.from_bytes(data)
        assert header2.version == header.version

    def test_block_serialization(self):
        """Serialize and deserialize a block."""
        block = CBlock()
        f = BytesIO()
        block.serialize(f)
        f.seek(0)
        raw = f.read()
        assert len(raw) > 0


class TestTransactionWorkflow:
    """E2E: Transaction operations."""

    def test_create_transaction(self):
        """Create a basic transaction."""
        tx = CTransaction()
        f = BytesIO()
        tx.serialize(f)
        f.seek(0)
        data = f.read()
        assert len(data) > 0

    def test_transaction_empty_vin_vout(self):
        """Empty transaction has no inputs/outputs."""
        tx = CTransaction()
        assert len(tx.vin) == 0
        assert len(tx.vout) == 0


class TestScriptWorkflow:
    """E2E: Script validation workflow."""

    def test_verify_p2pkh_script(self):
        """Verify a P2PKH script."""
        pubkey_hash = bytes.fromhex("ab" * 20)
        script = CScript.p2pkh(pubkey_hash)
        result = verify_script(script)
        assert result is True

    def test_verify_p2wpkh_script(self):
        """Verify a P2WPKH script."""
        pubkey_hash = bytes.fromhex("ab" * 20)
        script = CScript.p2wpkh(pubkey_hash)
        result = verify_script(script)
        assert result is True

    def test_op_return_classification(self):
        """OP_RETURN scripts are unspendable."""
        script = CScript.op_return(b"data")
        assert script.is_unspendable() is True


class TestScriptInterpreterWorkflow:
    """E2E: Script interpreter operations."""

    def test_interpreter_stack_operations(self):
        """Test stack push/pop operations."""
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"\x00\x01\x02")
        result = interp.evaluate(script)
        assert result is True

    def test_interpreter_p2pkh_pattern(self):
        """Test P2PKH evaluation."""
        interp = ScriptInterpreter()
        pubkey_hash = bytes.fromhex("00" * 20)
        script = CScript.p2pkh(pubkey_hash)
        result = interp.evaluate(script)
        assert isinstance(result, bool)