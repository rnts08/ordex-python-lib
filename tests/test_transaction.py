"""
Tests for transaction serialization.
"""

from io import BytesIO

import pytest

from ordex.primitives.transaction import COutPoint, CTxIn, CTxOut, CTransaction


class TestCOutPoint:
    def test_null(self):
        op = COutPoint()
        assert op.is_null()

    def test_not_null(self):
        op = COutPoint(b"\x01" * 32, 0)
        assert not op.is_null()

    def test_roundtrip(self):
        op = COutPoint(b"\xab" * 32, 42)
        buf = BytesIO()
        op.serialize(buf)
        buf.seek(0)
        op2 = COutPoint.deserialize(buf)
        assert op == op2


class TestCTxIn:
    def test_defaults(self):
        txin = CTxIn()
        assert txin.sequence == CTxIn.SEQUENCE_FINAL
        assert txin.prevout.is_null()

    def test_roundtrip(self):
        txin = CTxIn(
            prevout=COutPoint(b"\xab" * 32, 1),
            script_sig=b"\x04\xff\xff\xff\x1f",
            sequence=0xFFFFFFFE,
        )
        buf = BytesIO()
        txin.serialize(buf)
        buf.seek(0)
        txin2 = CTxIn.deserialize(buf)
        assert txin.prevout == txin2.prevout
        assert txin.sequence == txin2.sequence


class TestCTxOut:
    def test_roundtrip(self):
        txout = CTxOut(50_00000000, b"\x76\xa9\x14" + b"\x00" * 20 + b"\x88\xac")
        buf = BytesIO()
        txout.serialize(buf)
        buf.seek(0)
        txout2 = CTxOut.deserialize(buf)
        assert txout == txout2

    def test_null(self):
        txout = CTxOut()
        assert txout.is_null()


class TestCTransaction:
    def test_coinbase(self):
        tx = CTransaction(
            version=1,
            vin=[CTxIn(prevout=COutPoint(b"\x00" * 32, 0xFFFFFFFF), script_sig=b"\x04test")],
            vout=[CTxOut(50_00000000, b"\x76\xa9\x14" + b"\x00" * 20 + b"\x88\xac")],
            locktime=0,
        )
        assert tx.is_coinbase()

    def test_not_coinbase(self):
        tx = CTransaction(
            version=1,
            vin=[CTxIn(prevout=COutPoint(b"\x01" * 32, 0), script_sig=b"")],
            vout=[CTxOut(49_00000000, b"\x76\xa9\x14" + b"\x00" * 20 + b"\x88\xac")],
            locktime=0,
        )
        assert not tx.is_coinbase()

    def test_serialization_roundtrip(self):
        tx = CTransaction(
            version=2,
            vin=[CTxIn(prevout=COutPoint(b"\xab" * 32, 0), script_sig=b"\x00")],
            vout=[CTxOut(100000, b"\x76\xa9\x14" + b"\x00" * 20 + b"\x88\xac")],
            locktime=500000,
        )
        data = tx.to_bytes(allow_witness=False)
        tx2 = CTransaction.from_bytes(data, allow_witness=False)
        assert tx.version == tx2.version
        assert tx.locktime == tx2.locktime
        assert len(tx.vin) == len(tx2.vin)
        assert len(tx.vout) == len(tx2.vout)

    def test_txid_deterministic(self):
        tx = CTransaction(
            version=1,
            vin=[CTxIn(prevout=COutPoint(b"\x00" * 32, 0xFFFFFFFF), script_sig=b"test")],
            vout=[CTxOut(50_00000000, b"\x00")],
            locktime=0,
        )
        txid1 = tx.txid()
        txid2 = tx.txid()
        assert txid1 == txid2
        assert len(txid1) == 32
