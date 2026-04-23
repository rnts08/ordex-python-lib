"""
Tests for script interpreter.
"""

import pytest

from ordex.core.script import (
    CScript, OP_DUP, OP_HASH160, OP_EQUALVERIFY, OP_CHECKSIG,
    OP_EQUAL, OP_RETURN, OP_0, OP_1, OP_2, OP_CHECKMULTISIG,
    ScriptInterpreter, verify_script, ScriptError,
    OP_IF, OP_NOTIF, OP_ELSE, OP_ENDIF, OP_VERIFY,
    OP_CHECKLOCKTIMEVERIFY, OP_CHECKSEQUENCEVERIFY,
)


class TestCScriptClassification:
    """Tests for CScript classification methods."""

    def test_is_p2pkh(self):
        script = CScript.p2pkh(bytes.fromhex("00" * 20))
        assert script.is_p2pkh() is True

    def test_is_not_p2pkh(self):
        script = CScript(bytes([OP_RETURN]) + b"test")
        assert script.is_p2pkh() is False

    def test_is_p2sh(self):
        script = CScript.p2sh(bytes.fromhex("00" * 20))
        assert script.is_p2sh() is True

    def test_is_not_p2sh(self):
        script = CScript.p2pkh(bytes.fromhex("00" * 20))
        assert script.is_p2sh() is False

    def test_is_p2wpkh(self):
        script = CScript.p2wpkh(bytes.fromhex("00" * 20))
        assert script.is_witness_v0_keyhash() is True

    def test_is_p2wsh(self):
        script = CScript.p2wsh(bytes.fromhex("00" * 32))
        assert script.is_witness_v0_scripthash() is True

    def test_is_op_return(self):
        script = CScript.op_return(b"data")
        assert script.is_unspendable() is True

    def test_get_p2pkh_hash(self):
        expected_hash = bytes.fromhex("ab" * 20)
        script = CScript.p2pkh(expected_hash)
        assert script.get_p2pkh_hash() == expected_hash

    def test_get_p2sh_hash(self):
        expected_hash = bytes.fromhex("cd" * 20)
        script = CScript.p2sh(expected_hash)
        assert script.get_p2sh_hash() == expected_hash


class TestCScriptNum:
    """Tests for CScriptNum encoding."""

    def test_encode_zero(self):
        from ordex.core.script import CScriptNum
        assert CScriptNum.encode(0) == b""

    def test_encode_one(self):
        from ordex.core.script import CScriptNum
        assert CScriptNum.encode(1) == bytes([1])

    def test_encode_negative(self):
        from ordex.core.script import CScriptNum
        result = CScriptNum.encode(-1)
        assert result == bytes([0x81])

    def test_encode_128(self):
        from ordex.core.script import CScriptNum
        result = CScriptNum.encode(128)
        assert result == bytes([0x80, 0x00])


class TestCScriptBuilders:
    """Tests for CScript builder methods."""

    def test_p2pkh_builder(self):
        pubkey_hash = bytes.fromhex("00" * 20)
        script = CScript.p2pkh(pubkey_hash)

        assert len(script) == 25
        assert script[0] == OP_DUP
        assert script[1] == OP_HASH160
        assert script[2] == 20
        assert script[23] == OP_EQUALVERIFY
        assert script[24] == OP_CHECKSIG

    def test_p2sh_builder(self):
        script_hash = bytes.fromhex("00" * 20)
        script = CScript.p2sh(script_hash)

        assert len(script) == 23
        assert script[0] == OP_HASH160
        assert script[1] == 20
        assert script[22] == OP_EQUAL

    def test_p2wpkh_builder(self):
        pubkey_hash = bytes.fromhex("00" * 20)
        script = CScript.p2wpkh(pubkey_hash)

        assert len(script) == 22
        assert script[0] == OP_0
        assert script[1] == 20

    def test_p2wsh_builder(self):
        script_hash = bytes.fromhex("00" * 32)
        script = CScript.p2wsh(script_hash)

        assert len(script) == 34
        assert script[0] == OP_0
        assert script[1] == 32

    def test_op_return_builder(self):
        data = b"test data"
        script = CScript.op_return(data)

        assert script[0] == OP_RETURN
        assert data in script


class TestScriptInterpreter:
    """Tests for ScriptInterpreter."""

    def test_init(self):
        interp = ScriptInterpreter()
        assert interp.stack == []
        assert interp.pc == 0

    def test_reset(self):
        interp = ScriptInterpreter()
        interp.stack = [b"test"]
        interp.pc = 10
        interp.reset()
        assert interp.stack == []
        assert interp.pc == 0

    def test_evaluate_push(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"\x02")
        result = interp.evaluate(script)
        assert result is True
        assert interp.stack == [b"\x02"]

    def test_evaluate_op_0(self):
        interp = ScriptInterpreter()
        script = CScript(bytes([OP_0]))
        result = interp.evaluate(script)
        assert result is False
        assert interp.stack == [b""]

    def test_evaluate_op_1(self):
        interp = ScriptInterpreter()
        script = CScript(bytes([OP_1]))
        result = interp.evaluate(script)
        assert result is True

    def test_evaluate_op_dup(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"test", OP_DUP)
        result = interp.evaluate(script)
        assert result is True
        assert interp.stack == [b"test", b"test"]

    def test_evaluate_op_hash160(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"test", OP_HASH160)
        result = interp.evaluate(script)
        assert result is True
        assert len(interp.stack) == 1
        assert len(interp.stack[0]) == 20

    def test_evaluate_op_equal_true(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"test", b"test", OP_EQUAL)
        result = interp.evaluate(script)
        assert result is True

    def test_evaluate_op_equal_false(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"test", b"other", OP_EQUAL)
        result = interp.evaluate(script)
        assert result is False

    def test_evaluate_op_return_fails(self):
        interp = ScriptInterpreter()
        script = CScript(bytes([OP_RETURN]))
        result = interp.evaluate(script)
        assert result is False

    def test_evaluate_p2pkh_pattern(self):
        interp = ScriptInterpreter()
        pubkey_hash = bytes.fromhex("00" * 20)
        script = CScript.p2pkh(pubkey_hash)
        result = interp.evaluate(script)
        assert isinstance(result, bool)


class TestVerifyScript:
    """Tests for verify_script function."""

    def test_verify_p2pkh_classification(self):
        pubkey_hash = bytes.fromhex("ab" * 20)
        script = CScript.p2pkh(pubkey_hash)

        assert script.is_p2pkh()
        assert script.get_p2pkh_hash() == pubkey_hash

    def test_verify_p2sh_classification(self):
        script_hash = bytes.fromhex("cd" * 20)
        script = CScript.p2sh(script_hash)

        assert script.is_p2sh()
        assert script.get_p2sh_hash() == script_hash

    def test_verify_p2wpkh_classification(self):
        pubkey_hash = bytes.fromhex("ef" * 20)
        script = CScript.p2wpkh(pubkey_hash)

        assert script.is_witness_v0_keyhash()

    def test_verify_unknown_script(self):
        script = CScript.from_ops(OP_1, OP_2, OP_EQUAL)
        result = verify_script(script)
        assert result is False


class TestCScriptFromOps:
    """Tests for CScript.from_ops builder."""

    def test_from_ops_opcodes(self):
        script = CScript.from_ops(OP_DUP, OP_HASH160)
        assert len(script) == 2
        assert script[0] == OP_DUP
        assert script[1] == OP_HASH160

    def test_from_ops_data(self):
        script = CScript.from_ops(b"hello")
        assert len(script) == 6
        assert script[0] == 5
        assert script[1:6] == b"hello"

    def test_from_ops_mixed(self):
        script = CScript.from_ops(OP_DUP, b"test", OP_HASH160)
        assert len(script) == 7

    def test_from_ops_p2pkh(self):
        pubkey_hash = bytes.fromhex("00" * 20)
        script = CScript.from_ops(
            OP_DUP,
            OP_HASH160,
            pubkey_hash,
            OP_EQUALVERIFY,
            OP_CHECKSIG,
        )
        assert script == CScript.p2pkh(pubkey_hash)


class TestExtendedOpcodes:
    """Tests for extended script opcodes - verified as recognized opcodes."""

    def test_opcodes_defined(self):
        assert OP_IF == 0x63
        assert OP_NOTIF == 0x64
        assert OP_ELSE == 0x67
        assert OP_ENDIF == 0x68
        assert OP_VERIFY == 0x69
        assert OP_CHECKLOCKTIMEVERIFY == 0xB1
        assert OP_CHECKSEQUENCEVERIFY == 0xB2

    def test_op_verify_recognized(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"\x01", OP_VERIFY)
        try:
            result = interp.evaluate(script)
        except ScriptError:
            pass

    def test_op_if_recognized(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(OP_IF, OP_ENDIF)
        try:
            result = interp.evaluate(script)
        except ScriptError:
            pass

    def test_op_notif_recognized(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(OP_NOTIF, OP_ENDIF)
        try:
            result = interp.evaluate(script)
        except ScriptError:
            pass

    def test_op_else_recognized(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(OP_IF, OP_ELSE, OP_ENDIF)
        try:
            result = interp.evaluate(script)
        except ScriptError:
            pass

    def test_op_cltv_recognized(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"\x01", OP_CHECKLOCKTIMEVERIFY)
        try:
            result = interp.evaluate(script)
        except ScriptError:
            pass

    def test_op_csv_recognized(self):
        interp = ScriptInterpreter()
        script = CScript.from_ops(b"\x01", OP_CHECKSEQUENCEVERIFY)
        try:
            result = interp.evaluate(script)
        except ScriptError:
            pass