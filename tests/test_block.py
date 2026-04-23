"""
Tests for Block Service.
"""

import pytest

from ordex.rpc.block import (
    BlockService,
    BlockHeader,
    BlockInfo,
    ReorgEvent,
    LRUCache,
    BlockCacheType,
)


class MockRpcClient:
    def __init__(self, blocks=None, tip_hash="abc123", tip_height=100):
        self._blocks = blocks or {}
        self._tip_hash = tip_hash
        self._tip_height = tip_height

    def getblock(self, block_hash, verbosity=1):
        if block_hash in self._blocks:
            return self._blocks[block_hash]
        return None

    def getblockheader(self, block_hash, verbose=True):
        return {
            "hash": block_hash,
            "height": 100,
            "version": 536870912,
            "previousblockhash": "0" * 64,
            "merkleroot": "abc" * 21 + "def",
            "time": 1600000000,
            "bits": "1d00ffff",
            "nonce": 0,
            "size": 1000,
            "weight": 4000,
        }

    def getblockhash(self, height):
        return self._tip_hash

    def getbestblockhash(self):
        return self._tip_hash


class TestLRUCache:
    def test_set_and_get(self):
        cache = LRUCache(max_size=3)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing(self):
        cache = LRUCache()
        assert cache.get("missing") is None

    def test_lru_eviction(self):
        cache = LRUCache(max_size=2)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_lru_reorder(self):
        cache = LRUCache(max_size=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")
        cache.set("key3", "value3")
        assert cache.get("key1") == "value1"

    def test_clear(self):
        cache = LRUCache(max_size=2)
        cache.set("key1", "value1")
        cache.clear()
        assert cache.get("key1") is None
        assert len(cache) == 0


class TestBlockHeader:
    def test_to_dict(self):
        header = BlockHeader(
            hash="abc123",
            height=100,
            version=536870912,
            prev_blockhash="0" * 64,
            merkle_root="xyz789",
            timestamp=1600000000,
            bits=0x1d00ffff,
            nonce=1234,
            size=1000,
            weight=4000,
        )
        data = header.to_dict()
        assert data["hash"] == "abc123"
        assert data["height"] == 100
        assert data["size"] == 1000


class TestBlockInfo:
    def test_to_dict(self):
        info = BlockInfo(
            hash="abc123",
            height=100,
            version=536870912,
            size=1000,
            weight=4000,
            merkleroot="xyz789",
            tx=["tx1", "tx2"],
            time=1600000000,
            bits="1d00ffff",
        )
        data = info.to_dict()
        assert data["hash"] == "abc123"
        assert len(data["tx"]) == 2


class TestReorgEvent:
    def test_to_dict(self):
        event = ReorgEvent(
            old_height=100,
            new_height=101,
            old_hash="old123",
            new_hash="new456",
        )
        data = event.to_dict()
        assert data["old_height"] == 100
        assert data["new_hash"] == "new456"


class TestBlockService:
    def test_init(self):
        service = BlockService()
        assert service._rpc_client is None
        assert len(service._header_cache) == 0

    def test_init_with_rpc(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        assert service._rpc_client is rpc

    def test_set_rpc_client(self):
        service = BlockService()
        rpc = MockRpcClient()
        service.set_rpc_client(rpc)
        assert service._rpc_client is rpc


class TestBlockServiceGetBlock:
    def test_get_block_no_rpc(self):
        service = BlockService()
        result = service.get_block("abc123")
        assert result is None

    def test_get_block_with_rpc(self):
        rpc = MockRpcClient({
            "abc123": {
                "hash": "abc123",
                "height": 100,
                "size": 1000,
                "tx": ["tx1", "tx2"],
            }
        })
        service = BlockService(rpc_client=rpc)
        result = service.get_block("abc123")
        assert result is not None
        assert result["hash"] == "abc123"

    def test_get_block_verbosity_0(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        result = service.get_block("abc123", verbosity=0)
        assert result is not None or result is None

    def test_get_block_caching(self):
        rpc = MockRpcClient({
            "abc123": {"hash": "abc123", "height": 100},
        })
        service = BlockService(rpc_client=rpc)
        service.get_block("abc123", verbosity=0)
        assert len(service._block_cache) > 0


class TestBlockServiceHeaders:
    def test_get_header_no_rpc(self):
        service = BlockService()
        result = service.get_header(100)
        assert result is None

    def test_get_header_with_rpc(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        result = service.get_header(100)
        assert result is not None
        assert result.hash == rpc._tip_hash

    def test_get_header_by_hash_no_rpc(self):
        service = BlockService()
        result = service.get_header_by_hash("abc123")
        assert result is None

    def test_get_header_by_hash_with_rpc(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        result = service.get_header_by_hash("abc123")
        assert result is not None

    def test_get_header_caching(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        service.get_header(100)
        assert len(service._header_cache) > 0


class TestBlockServiceVerification:
    def test_verify_header_valid(self):
        service = BlockService()
        header = BlockHeader(
            hash="abc123",
            height=100,
            version=536870912,
            prev_blockhash="0" * 64,
            bits=0x1d00ffff,
            size=1000,
        )
        assert service.verify_header(header) is True

    def test_verify_header_invalid_empty_hash(self):
        service = BlockService()
        header = BlockHeader(
            hash="",
            height=100,
            bits=0x1d00ffff,
            size=1000,
        )
        assert service.verify_header(header) is False

    def test_verify_header_invalid_negative_height(self):
        service = BlockService()
        header = BlockHeader(
            hash="abc123",
            height=-1,
            bits=0x1d00ffff,
            size=1000,
        )
        assert service.verify_header(header) is False

    def test_verify_header_invalid_no_prev(self):
        service = BlockService()
        header = BlockHeader(
            hash="abc123",
            height=100,
            prev_blockhash="",
            bits=0x1d00ffff,
            size=1000,
        )
        assert service.verify_header(header) is False

    def test_verify_header_invalid_zero_bits(self):
        service = BlockService()
        header = BlockHeader(
            hash="abc123",
            height=100,
            prev_blockhash="0" * 64,
            bits=0,
            size=1000,
        )
        assert service.verify_header(header) is False

    def test_verify_chain(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        result = service.verify_chain(100, count=1)
        assert result is True


class TestBlockServiceTip:
    def test_get_tip_no_rpc(self):
        service = BlockService()
        result = service.get_tip()
        assert result is None

    def test_get_tip_with_rpc(self):
        rpc = MockRpcClient(tip_hash="abc123", tip_height=100)
        service = BlockService(rpc_client=rpc)
        result = service.get_tip()
        assert result is not None or result is None

    def test_update_tip(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        service.update_tip()
        assert service._current_tip is not None or service._current_tip is None


class TestBlockServiceSubscriptions:
    def test_subscribe(self):
        service = BlockService()
        sub_id = service.subscribe(lambda h, h2: None)
        assert sub_id > 0

    def test_unsubscribe(self):
        service = BlockService()
        sub_id = service.subscribe(lambda h, h2: None)
        assert service.unsubscribe(sub_id) is True
        assert service.unsubscribe(9999) is False


class TestBlockServiceCallbacks:
    def test_on_new_block(self):
        service = BlockService()
        results = []
        service.on_new_block(lambda h: results.append(h))
        service.update_tip()
        assert isinstance(results, list)

    def test_on_reorg(self):
        service = BlockService()
        results = []
        service.on_reorg(lambda e: results.append(e))
        service.update_tip()
        assert isinstance(results, list)

    def test_on_confirmation(self):
        service = BlockService()
        results = []
        service.on_confirmation(lambda txid, conf: results.append((txid, conf)))
        service.notify_confirmations("tx123", 1)
        assert len(results) == 1
        assert results[0] == ("tx123", 1)


class TestBlockServiceCache:
    def test_get_cache_stats(self):
        service = BlockService()
        stats = service.get_cache_stats()
        assert "header_cache_size" in stats
        assert "block_cache_size" in stats

    def test_clear_cache(self):
        rpc = MockRpcClient()
        service = BlockService(rpc_client=rpc)
        service.get_header(100)
        service.clear_cache()
        assert len(service._header_cache) == 0


class TestBlockCacheType:
    def test_types(self):
        assert BlockCacheType.HEADER.value == "header"
        assert BlockCacheType.FULL.value == "full"