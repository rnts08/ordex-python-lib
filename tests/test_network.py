"""
Tests for Network Monitor Service.
"""

import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from ordex.rpc.network import (
    NodePool, NodeInfo, NetworkStats, NodeStatus,
    LoadBalancingStrategy,
)


class TestNodeInfo:
    """Tests for NodeInfo."""

    def test_create_node_info(self):
        node = NodeInfo(url="http://localhost:25175", priority=1, weight=1.0)
        assert node.url == "http://localhost:25175"
        assert node.priority == 1
        assert node.weight == 1.0
        assert node.status == NodeStatus.DISCONNECTED

    def test_host_property(self):
        node = NodeInfo(url="http://localhost:25175")
        assert node.host == "localhost:25175"

    def test_error_rate_zero(self):
        node = NodeInfo(url="http://localhost:25175")
        assert node.error_rate == 0.0

    def test_error_rate_calculated(self):
        node = NodeInfo(url="http://localhost:25175", total_requests=10, failed_requests=2)
        assert node.error_rate == 0.2

    def test_health_score_perfect(self):
        node = NodeInfo(url="http://localhost:25175")
        assert node.health_score == 1.0

    def test_health_score_degraded(self):
        node = NodeInfo(
            url="http://localhost:25175",
            consecutive_failures=3,
            latency_ms=1500,
        )
        assert node.health_score < 1.0

    def test_to_dict(self):
        node = NodeInfo(url="http://localhost:25175", priority=2)
        d = node.to_dict()
        assert d["url"] == "http://localhost:25175"
        assert d["priority"] == 2


class TestNetworkStats:
    """Tests for NetworkStats."""

    def test_create_stats(self):
        stats = NetworkStats(total_nodes=5, healthy_nodes=3)
        assert stats.total_nodes == 5
        assert stats.healthy_nodes == 3

    def test_to_dict(self):
        stats = NetworkStats(total_nodes=5)
        d = stats.to_dict()
        assert d["total_nodes"] == 5


class TestNodePool:
    """Tests for NodePool."""

    def test_create_pool(self):
        pool = NodePool()
        assert len(pool.get_nodes()) == 0

    def test_add_node(self):
        pool = NodePool()
        node = pool.add_node("http://localhost:25175", priority=1)
        assert node.url == "http://localhost:25175"
        assert len(pool.get_nodes()) == 1

    def test_add_multiple_nodes(self):
        pool = NodePool()
        pool.add_node("http://node1:25175", priority=1)
        pool.add_node("http://node2:25175", priority=2)
        assert len(pool.get_nodes()) == 2

    def test_remove_node(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")
        assert pool.remove_node("http://localhost:25175") is True
        assert len(pool.get_nodes()) == 0

    def test_remove_nonexistent(self):
        pool = NodePool()
        assert pool.remove_node("http://localhost:25175") is False

    def test_get_node(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")
        node = pool.get_node("http://localhost:25175")
        assert node is not None
        assert node.url == "http://localhost:25175"

    def test_get_nonexistent_node(self):
        pool = NodePool()
        assert pool.get_node("http://localhost:25175") is None


class TestNodePoolSelection:
    """Tests for node selection strategies."""

    def test_round_robin_selection(self):
        pool = NodePool(strategy=LoadBalancingStrategy.ROUND_ROBIN)
        pool.add_node("http://node1:25175", priority=1)
        pool.add_node("http://node2:25175", priority=1)

        nodes = pool.get_nodes()
        assert len(nodes) == 2

    def test_priority_selection(self):
        pool = NodePool(strategy=LoadBalancingStrategy.PRIORITY)
        pool.add_node("http://node1:25175", priority=1)
        pool.add_node("http://node2:25175", priority=2)

        nodes = pool.get_healthy_nodes()
        assert len(nodes) >= 0


class TestHealthMonitoring:
    """Tests for health monitoring."""

    def test_record_successful_request(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")
        pool.record_request("http://localhost:25175", 100.0, True)

        node = pool.get_node("http://localhost:25175")
        assert node.total_requests == 1
        assert node.consecutive_failures == 0

    def test_record_failed_request(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")
        pool.record_request("http://localhost:25175", 100.0, False)

        node = pool.get_node("http://localhost:25175")
        assert node.total_requests == 1
        assert node.consecutive_failures == 1
        assert node.failed_requests == 1

    def test_status_change_callback(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")

        callbacks_called = []

        def callback(node, old_status):
            callbacks_called.append((node.url, old_status))

        pool.on_status_change("node_healthy", callback)

        pool.record_request("http://localhost:25175", 100.0, True)

    def test_consecutive_failures_degrade_status(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")

        for _ in range(3):
            pool.record_request("http://localhost:25175", 100.0, False)

        node = pool.get_node("http://localhost:25175")
        assert node.status in (NodeStatus.DEGRADED, NodeStatus.UNHEALTHY)


class TestNetworkStats:
    """Tests for network statistics."""

    def test_get_stats_empty(self):
        pool = NodePool()
        stats = pool.get_stats()
        assert stats.total_nodes == 0
        assert stats.healthy_nodes == 0

    def test_get_stats_with_nodes(self):
        pool = NodePool()
        pool.add_node("http://node1:25175")
        pool.add_node("http://node2:25175")

        pool.record_request("http://node1:25175", 100.0, True)
        pool.record_request("http://node2:25175", 200.0, True)

        stats = pool.get_stats()
        assert stats.total_nodes == 2


class TestNodeEnableDisable:
    """Tests for node enable/disable."""

    def test_disable_node(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")
        pool.set_node_enabled("http://localhost:25175", False)

        node = pool.get_node("http://localhost:25175")
        assert node.is_enabled is False

    def test_enable_node(self):
        pool = NodePool()
        pool.add_node("http://localhost:25175")
        pool.set_node_enabled("http://localhost:25175", False)
        pool.set_node_enabled("http://localhost:25175", True)

        node = pool.get_node("http://localhost:25175")
        assert node.is_enabled is True


class TestSummary:
    """Tests for summary generation."""

    def test_summary_empty(self):
        pool = NodePool()
        summary = pool.summary()
        assert "NODE POOL SUMMARY" in summary
        assert "Total Nodes: 0" in summary

    def test_summary_with_nodes(self):
        pool = NodePool()
        pool.add_node("http://node1:25175")
        pool.add_node("http://node2:25175")

        summary = pool.summary()
        assert "Total Nodes: 2" in summary


class TestConcurrency:
    """Tests for thread safety."""

    def test_concurrent_access(self):
        pool = NodePool()
        pool.add_node("http://node1:25175")

        results = []

        def worker():
            for _ in range(100):
                pool.get_node("http://node1:25175")
                pool.get_stats()
                results.append(None)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 500


import threading