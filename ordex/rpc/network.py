"""
Network Monitor Service for multi-node RPC management.

Provides node pool management, health checks, automatic failover,
and load balancing for RPC connections.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ordex.rpc.client import RpcClient

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """RPC node status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DISCONNECTED = "disconnected"


class LoadBalancingStrategy(Enum):
    """Load balancing strategy."""
    ROUND_ROBIN = "round_robin"
    PRIORITY = "priority"
    LATENCY = "latency"
    RANDOM = "random"


@dataclass
class NodeInfo:
    """Information about an RPC node."""
    url: str
    priority: int = 1
    weight: float = 1.0
    status: NodeStatus = NodeStatus.DISCONNECTED
    latency_ms: float = 0.0
    last_check: Optional[str] = None
    consecutive_failures: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    is_enabled: bool = True

    @property
    def host(self) -> str:
        parsed = urlparse(self.url)
        return parsed.netloc or self.url

    @property
    def error_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests

    @property
    def health_score(self) -> float:
        """Calculate health score (1.0 = perfect, 0.0 = unhealthy)."""
        score = 1.0
        score -= self.error_rate * 0.5
        score -= min(self.consecutive_failures * 0.1, 0.3)
        if self.latency_ms > 1000:
            score -= 0.2
        return max(0.0, score)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "priority": self.priority,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check,
            "health_score": self.health_score,
            "is_enabled": self.is_enabled,
        }


@dataclass
class NetworkStats:
    """Network-wide statistics."""
    total_nodes: int = 0
    healthy_nodes: int = 0
    degraded_nodes: int = 0
    unhealthy_nodes: int = 0
    disconnected_nodes: int = 0
    average_latency_ms: float = 0.0
    average_error_rate: float = 0.0
    total_requests: int = 0
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_nodes": self.total_nodes,
            "healthy_nodes": self.healthy_nodes,
            "degraded_nodes": self.degraded_nodes,
            "unhealthy_nodes": self.unhealthy_nodes,
            "disconnected_nodes": self.disconnected_nodes,
            "average_latency_ms": self.average_latency_ms,
            "average_error_rate": self.average_error_rate,
            "total_requests": self.total_requests,
            "last_updated": self.last_updated,
        }


class NodePool:
    """Manages a pool of RPC nodes with health checks and failover.

    Features:
    - Multiple RPC endpoints
    - Health monitoring with configurable intervals
    - Automatic failover to healthy nodes
    - Load balancing strategies
    - Request tracking per node
    """

    def __init__(
        self,
        nodes: Optional[List[Dict[str, Any]]] = None,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.PRIORITY,
        health_check_interval: int = 30,
        timeout: int = 30,
    ) -> None:
        self._nodes: Dict[str, NodeInfo] = {}
        self._strategy = strategy
        self._health_check_interval = health_check_interval
        self._timeout = timeout
        self._lock = threading.Lock()
        self._round_robin_index = 0
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_health_check = threading.Event()
        self._callbacks: Dict[str, List[Callable]] = {
            "node_healthy": [],
            "node_degraded": [],
            "node_unhealthy": [],
            "node_disconnected": [],
        }

        if nodes:
            for node in nodes:
                self.add_node(
                    url=node["url"],
                    priority=node.get("priority", 1),
                    weight=node.get("weight", 1.0),
                )

    def add_node(self, url: str, priority: int = 1, weight: float = 1.0) -> NodeInfo:
        """Add a node to the pool.

        Args:
            url: RPC endpoint URL
            priority: Priority for PRIORITY strategy (higher = preferred)
            weight: Weight for weighted strategies

        Returns:
            NodeInfo for the added node
        """
        with self._lock:
            node = NodeInfo(url=url, priority=priority, weight=weight)
            self._nodes[url] = node
            logger.info("Added node: %s (priority=%d)", url, priority)
            return node

    def remove_node(self, url: str) -> bool:
        """Remove a node from the pool.

        Args:
            url: RPC endpoint URL

        Returns:
            True if node was removed, False if not found
        """
        with self._lock:
            if url in self._nodes:
                del self._nodes[url]
                logger.info("Removed node: %s", url)
                return True
            return False

    def get_client(self) -> Optional["RpcClient"]:
        """Get an RpcClient for a healthy node.

        Returns:
            RpcClient configured for the selected node, or None if no healthy nodes
        """
        node = self._select_node()
        if not node:
            return None

        from ordex.rpc.client import RpcClient
        parsed = urlparse(node.url)

        return RpcClient(
            url=node.url,
            username=parsed.username or "rpcuser",
            password=parsed.password or "rpcpass",
            timeout=self._timeout,
        )

    def _select_node(self) -> Optional[NodeInfo]:
        """Select a node based on the load balancing strategy."""
        with self._lock:
            healthy = [n for n in self._nodes.values() if n.is_enabled and n.status != NodeStatus.UNHEALTHY]
            if not healthy:
                return None

            if self._strategy == LoadBalancingStrategy.ROUND_ROBIN:
                return self._round_robin_select(healthy)
            elif self._strategy == LoadBalancingStrategy.PRIORITY:
                return self._priority_select(healthy)
            elif self._strategy == LoadBalancingStrategy.LATENCY:
                return self._latency_select(healthy)
            elif self._strategy == LoadBalancingStrategy.RANDOM:
                import random
                return random.choice(healthy)
            return healthy[0]

    def _round_robin_select(self, nodes: List[NodeInfo]) -> NodeInfo:
        idx = self._round_robin_index % len(nodes)
        self._round_robin_index += 1
        return nodes[idx]

    def _priority_select(self, nodes: List[NodeInfo]) -> NodeInfo:
        return max(nodes, key=lambda n: n.priority * n.health_score)

    def _latency_select(self, nodes: List[NodeInfo]) -> NodeInfo:
        available = [n for n in nodes if n.latency_ms < 5000]
        if not available:
            return nodes[0]
        return min(available, key=lambda n: n.latency_ms)

    def get_node(self, url: str) -> Optional[NodeInfo]:
        """Get information about a specific node."""
        return self._nodes.get(url)

    def get_nodes(self) -> List[NodeInfo]:
        """Get all nodes in the pool."""
        return list(self._nodes.values())

    def get_healthy_nodes(self) -> List[NodeInfo]:
        """Get nodes that are healthy or degraded."""
        return [n for n in self._nodes.values() if n.status in (NodeStatus.HEALTHY, NodeStatus.DEGRADED)]

    def get_stats(self) -> NetworkStats:
        """Get network-wide statistics."""
        stats = NetworkStats(total_nodes=len(self._nodes))

        for node in self._nodes.values():
            if node.status == NodeStatus.HEALTHY:
                stats.healthy_nodes += 1
            elif node.status == NodeStatus.DEGRADED:
                stats.degraded_nodes += 1
            elif node.status == NodeStatus.UNHEALTHY:
                stats.unhealthy_nodes += 1
            elif node.status == NodeStatus.DISCONNECTED:
                stats.disconnected_nodes += 1

            stats.total_requests += node.total_requests
            if node.latency_ms > 0:
                stats.average_latency_ms += node.latency_ms
            stats.average_error_rate += node.error_rate

        if stats.healthy_nodes > 0:
            stats.average_latency_ms /= stats.healthy_nodes
            stats.average_error_rate /= stats.healthy_nodes

        stats.last_updated = datetime.now(timezone.utc).isoformat()
        return stats

    def record_request(self, url: str, latency_ms: float, success: bool) -> None:
        """Record a request result for a node.

        Args:
            url: Node URL
            latency_ms: Request latency
            success: Whether the request succeeded
        """
        with self._lock:
            node = self._nodes.get(url)
            if not node:
                return

            node.total_requests += 1
            node.latency_ms = latency_ms
            node.last_check = datetime.now(timezone.utc).isoformat()

            if success:
                node.consecutive_failures = 0
            else:
                node.consecutive_failures += 1
                node.failed_requests += 1

            old_status = node.status
            node.status = self._evaluate_status(node)

            if node.status != old_status:
                self._emit_status_change(node, old_status)

    def _evaluate_status(self, node: NodeInfo) -> NodeStatus:
        """Evaluate node status based on metrics."""
        if node.consecutive_failures >= 5:
            return NodeStatus.UNHEALTHY
        elif node.consecutive_failures >= 2:
            return NodeStatus.DEGRADED
        elif node.error_rate > 0.1:
            return NodeStatus.DEGRADED
        elif node.latency_ms > 2000:
            return NodeStatus.DEGRADED
        return NodeStatus.HEALTHY

    def _emit_status_change(self, node: NodeInfo, old_status: NodeStatus) -> None:
        """Emit callbacks for status changes."""
        event = None
        if node.status == NodeStatus.HEALTHY:
            event = "node_healthy"
        elif node.status == NodeStatus.DEGRADED:
            event = "node_degraded"
        elif node.status == NodeStatus.UNHEALTHY:
            event = "node_unhealthy"
        elif node.status == NodeStatus.DISCONNECTED:
            event = "node_disconnected"

        if event and event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    callback(node, old_status)
                except Exception as e:
                    logger.error("Callback error: %s", e)

    def on_status_change(
        self,
        status: str,
        callback: Callable[[NodeInfo, NodeStatus], None],
    ) -> None:
        """Register a callback for status changes.

        Args:
            status: Status to listen for (node_healthy, node_degraded, etc.)
            callback: Function to call when status changes
        """
        if status in self._callbacks:
            self._callbacks[status].append(callback)

    def start_health_checks(self, rpc_factory: Callable[[str], "RpcClient"]) -> None:
        """Start background health checks.

        Args:
            rpc_factory: Function that creates RpcClient from URL
        """
        if self._health_check_thread and self._health_check_thread.is_alive():
            return

        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            args=(rpc_factory,),
            daemon=True,
        )
        self._health_check_thread.start()
        logger.info("Started health check thread")

    def _health_check_loop(self, rpc_factory: Callable[[str], "RpcClient"]) -> None:
        """Background health check loop."""
        while not self._stop_health_check.is_set():
            for url, node in list(self._nodes.items()):
                if not node.is_enabled:
                    continue

                start = time.time()
                try:
                    client = rpc_factory(url)
                    client.getblockchaininfo()
                    latency = (time.time() - start) * 1000
                    self.record_request(url, latency, True)
                except Exception as e:
                    latency = (time.time() - start) * 1000
                    self.record_request(url, latency, False)
                    logger.debug("Health check failed for %s: %s", url, e)

            self._stop_health_check.wait(self._health_check_interval)

    def stop_health_checks(self) -> None:
        """Stop background health checks."""
        if self._health_check_thread:
            self._stop_health_check.set()
            self._health_check_thread.join(timeout=5)
            logger.info("Stopped health check thread")

    def set_node_enabled(self, url: str, enabled: bool) -> bool:
        """Enable or disable a node.

        Args:
            url: Node URL
            enabled: Whether to enable the node

        Returns:
            True if node was found
        """
        with self._lock:
            node = self._nodes.get(url)
            if node:
                node.is_enabled = enabled
                return True
            return False

    def summary(self) -> str:
        """Get a human-readable summary."""
        stats = self.get_stats()
        healthy = self.get_healthy_nodes()

        lines = [
            "=" * 50,
            "NODE POOL SUMMARY",
            "=" * 50,
            f"Total Nodes: {stats.total_nodes}",
            f"Healthy: {stats.healthy_nodes}",
            f"Degraded: {stats.degraded_nodes}",
            f"Unhealthy: {stats.unhealthy_nodes}",
            f"Avg Latency: {stats.average_latency_ms:.0f}ms",
            f"Avg Error Rate: {stats.average_error_rate:.1%}",
            "",
            "ACTIVE NODES:",
        ]

        for node in healthy:
            lines.append(f"  [{node.status.value}] {node.url} ({node.latency_ms:.0f}ms)")

        lines.append("=" * 50)
        return "\n".join(lines)