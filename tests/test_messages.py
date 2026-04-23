"""
Tests for P2P network messages.
"""

import struct
from io import BytesIO

import pytest

from ordex.net.messages import (
    MsgVersion, MsgPing, MsgPong, MsgInv, MsgGetData,
    MsgGetHeaders, MsgHeaders, MsgMerkleBlock,
    MsgAddr, MsgMempool, CAddress,
)
from ordex.net.protocol import CInv, InvType, ServiceFlags
from ordex.primitives.block import CBlockHeader


class TestMsgGetHeaders:
    """Tests for MsgGetHeaders serialization/deserialization."""

    def test_serialize_deserialize(self):
        msg = MsgGetHeaders(
            version=70016,
            block_locator_hashes=[bytes.fromhex("00" * 32), bytes.fromhex("01" * 32)],
            hash_stop=bytes.fromhex("ff" * 32),
        )

        data = msg.to_bytes()
        restored = MsgGetHeaders.deserialize(BytesIO(data))

        assert restored.version == msg.version
        assert restored.block_locator_hashes == msg.block_locator_hashes
        assert restored.hash_stop == msg.hash_stop

    def test_empty_locator(self):
        msg = MsgGetHeaders(
            version=70016,
            block_locator_hashes=[],
            hash_stop=bytes.fromhex("00" * 32),
        )

        data = msg.to_bytes()
        restored = MsgGetHeaders.deserialize(BytesIO(data))

        assert restored.block_locator_hashes == []
        assert restored.hash_stop == bytes.fromhex("00" * 32)


class TestMsgHeaders:
    """Tests for MsgHeaders serialization/deserialization."""

    def test_serialize_deserialize(self):
        headers = [
            CBlockHeader(
                version=1,
                hash_prev_block=bytes.fromhex("00" * 32),
                hash_merkle_root=bytes.fromhex("01" * 32),
                time=1234567890,
                bits=0x1e0ffff0,
                nonce=12345,
            ),
            CBlockHeader(
                version=2,
                hash_prev_block=bytes.fromhex("01" * 32),
                hash_merkle_root=bytes.fromhex("02" * 32),
                time=1234567891,
                bits=0x1e0ffff0,
                nonce=12346,
            ),
        ]
        msg = MsgHeaders(headers)

        data = msg.to_bytes()
        restored = MsgHeaders.deserialize(BytesIO(data))

        assert len(restored.headers) == 2
        assert restored.headers[0].version == headers[0].version
        assert restored.headers[1].version == headers[1].version

    def test_empty_headers(self):
        msg = MsgHeaders(headers=[])

        data = msg.to_bytes()
        restored = MsgHeaders.deserialize(BytesIO(data))

        assert len(restored.headers) == 0


class TestMsgMerkleBlock:
    """Tests for MsgMerkleBlock serialization/deserialization."""

    def test_serialize_deserialize(self):
        header = CBlockHeader(
            version=1,
            hash_prev_block=bytes.fromhex("00" * 32),
            hash_merkle_root=bytes.fromhex("01" * 32),
            time=1234567890,
            bits=0x1e0ffff0,
            nonce=12345,
        )
        msg = MsgMerkleBlock(
            header=header,
            transaction_count=10,
            hashes=[bytes.fromhex("aa" * 32), bytes.fromhex("bb" * 32)],
            flags=bytes([0x01, 0x02]),
        )

        data = msg.to_bytes()
        restored = MsgMerkleBlock.deserialize(BytesIO(data))

        assert restored.transaction_count == 10
        assert len(restored.hashes) == 2
        assert restored.flags == bytes([0x01, 0x02])
        assert restored.header.version == 1

    def test_empty_merkle_block(self):
        header = CBlockHeader()
        msg = MsgMerkleBlock(
            header=header,
            transaction_count=0,
            hashes=[],
            flags=b"",
        )

        data = msg.to_bytes()
        restored = MsgMerkleBlock.deserialize(BytesIO(data))

        assert restored.transaction_count == 0
        assert len(restored.hashes) == 0
        assert restored.flags == b""


class TestMsgVersion:
    """Tests for MsgVersion serialization/deserialization."""

    def test_serialize_deserialize(self):
        msg = MsgVersion(
            version=70016,
            services=ServiceFlags.NODE_NETWORK,
            timestamp=1234567890,
            start_height=100,
            relay=True,
        )

        data = msg.to_bytes()
        restored = MsgVersion.deserialize(BytesIO(data))

        assert restored.version == msg.version
        assert restored.services == msg.services
        assert restored.timestamp == msg.timestamp
        assert restored.start_height == msg.start_height
        assert restored.relay == msg.relay


class TestMsgInv:
    """Tests for MsgInv serialization/deserialization."""

    def test_serialize_deserialize(self):
        inv = [
            CInv(InvType.MSG_TX, bytes.fromhex("ab" * 32)),
            CInv(InvType.MSG_BLOCK, bytes.fromhex("cd" * 32)),
        ]
        msg = MsgInv(inventory=inv)

        data = msg.to_bytes()
        restored = MsgInv.deserialize(BytesIO(data))

        assert len(restored.inventory) == 2
        assert restored.inventory[0].is_tx()
        assert restored.inventory[1].is_block()

    def test_empty_inventory(self):
        msg = MsgInv(inventory=[])

        data = msg.to_bytes()
        restored = MsgInv.deserialize(BytesIO(data))

        assert len(restored.inventory) == 0


class TestMsgPing:
    """Tests for MsgPing serialization/deserialization."""

    def test_serialize_deserialize(self):
        msg = MsgPing(nonce=0x1234567890abcdef)

        data = msg.to_bytes()
        restored = MsgPing.deserialize(BytesIO(data))

        assert restored.nonce == msg.nonce


class TestMsgPong:
    """Tests for MsgPong serialization/deserialization."""

    def test_serialize_deserialize(self):
        msg = MsgPong(nonce=0x1234567890abcdef)

        data = msg.to_bytes()
        restored = MsgPong.deserialize(BytesIO(data))

        assert restored.nonce == msg.nonce


class TestCAddress:
    """Tests for CAddress serialization/deserialization."""

    def test_serialize_deserialize_with_timestamp(self):
        addr = CAddress(
            services=1,
            ip=bytes([127, 0, 0, 1] + [0] * 12),
            port=8333,
            timestamp=1234567890,
        )

        data = addr.to_bytes()
        restored = CAddress.deserialize(BytesIO(data), has_timestamp=True)

        assert restored.services == addr.services
        assert restored.ip == addr.ip
        assert restored.port == addr.port
        assert restored.timestamp == addr.timestamp

    def test_serialize_deserialize_without_timestamp(self):
        addr = CAddress(
            services=1,
            ip=bytes([127, 0, 0, 1] + [0] * 12),
            port=8333,
        )

        data = addr.to_bytes()
        restored = CAddress.deserialize(BytesIO(data), has_timestamp=False)

        assert restored.services == addr.services
        assert restored.port == addr.port
        assert restored.timestamp is None


class TestMsgAddr:
    """Tests for MsgAddr serialization/deserialization."""

    def test_serialize_deserialize(self):
        addresses = [
            CAddress(
                services=1,
                ip=bytes([127, 0, 0, 1] + [0] * 12),
                port=8333,
                timestamp=1234567890,
            ),
            CAddress(
                services=0,
                ip=bytes([192, 168, 1, 1] + [0] * 12),
                port=9333,
                timestamp=1234567891,
            ),
        ]
        msg = MsgAddr(addresses=addresses)

        data = msg.to_bytes()
        restored = MsgAddr.deserialize(BytesIO(data))

        assert len(restored.addresses) == 2
        assert restored.addresses[0].port == 8333
        assert restored.addresses[1].port == 9333

    def test_empty_addresses(self):
        msg = MsgAddr(addresses=[])

        data = msg.to_bytes()
        restored = MsgAddr.deserialize(BytesIO(data))

        assert len(restored.addresses) == 0


class TestMsgMempool:
    """Tests for MsgMempool serialization/deserialization."""

    def test_serialize_deserialize(self):
        msg = MsgMempool()

        data = msg.to_bytes()
        assert data == b""

        restored = MsgMempool.deserialize(BytesIO(data))
        assert isinstance(restored, MsgMempool)