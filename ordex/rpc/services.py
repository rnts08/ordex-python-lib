"""
Unified Service Container for Ordex RPC Services.

Provides a single interface to initialize and access all RPC services,
manages service dependencies, and coordinates between services.

Usage:
    from ordex.rpc.services import OrdexServices

    services = OrdexServices(config={
        "nodes": [
            {"url": "http://localhost:8332", "user": "user", "password": "pass"},
        ]
    })

    # Access services
    mempool = services.mempool
    blocks = services.blocks
    transactions = services.transactions
    address = services.address
    tracker = services.tracker
    notifications = services.notifications
    health = services.health
    network = services.network
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OrdexConfig:
    """Configuration for Ordex RPC Services."""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    rpc_user: str = ""
    rpc_password: str = ""
    wallet_directory: str = ""
    cache_size: int = 1000
    check_interval: int = 30
    gap_limit: int = 20
    fee_strategy: str = "economic"


class OrdexServices:
    """Unified container for all RPC services.

    Provides thread-safe access to all services with proper initialization
    and dependency management.

    Usage:
        services = OrdexServices(config={"nodes": [...]})
        mempool = services.mempool.get_fees()
        blocks = services.blocks.get_tip()
    """

    def __init__(self, config: Optional[OrdexConfig] = None) -> None:
        self._config = config or OrdexConfig()
        self._lock = threading.Lock()
        self._initialized = False
        self._rpc_client = None
        self._network = None
        self._health = None
        self._mempool = None
        self._blocks = None
        self._address = None
        self._transactions = None
        self._tracker = None
        self._notifications = None

    def initialize(self) -> None:
        """Initialize all services with proper dependency order."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            logger.info("Initializing Ordex RPC Services...")

            self._setup_network()
            self._setup_health()
            self._setup_mempool()
            self._setup_blocks()
            self._setup_address()
            self._setup_transactions()
            self._setup_tracker()
            self._setup_notifications()

            self._initialized = True
            logger.info("Ordex RPC Services initialized successfully")

    def _setup_network(self) -> None:
        """Setup Network Monitor service."""
        from ordex.rpc.network import NodePool

        nodes = self._config.nodes or [{"url": "http://localhost:8332"}]
        self._network = NodePool(nodes=nodes)
        self._rpc_client = self._network.get_client()
        logger.debug("Network service initialized")

    def _setup_health(self) -> None:
        """Setup Health Monitor service."""
        from ordex.rpc.health import HealthMonitor, ComponentType

        self._health = HealthMonitor(check_interval=self._config.check_interval)
        self._health.register_component("network", ComponentType.NETWORK)
        logger.debug("Health service initialized")

    def _setup_mempool(self) -> None:
        """Setup Mempool service."""
        from ordex.rpc.mempool import MempoolService

        self._mempool = MempoolService(rpc_client=self._rpc_client)
        logger.debug("Mempool service initialized")

    def _setup_blocks(self) -> None:
        """Setup Block service."""
        from ordex.rpc.block import BlockService

        self._blocks = BlockService(
            rpc_client=self._rpc_client,
            cache_size=self._config.cache_size,
        )
        logger.debug("Block service initialized")

    def _setup_address(self) -> None:
        """Setup Address service."""
        from ordex.rpc.address import AddressService

        self._address = AddressService(
            rpc_client=self._rpc_client,
            gap_limit=self._config.gap_limit,
        )
        logger.debug("Address service initialized")

    def _setup_transactions(self) -> None:
        """Setup Transaction service."""
        from ordex.rpc.transaction import TransactionService

        self._transactions = TransactionService(rpc_client=self._rpc_client)
        logger.debug("Transaction service initialized")

    def _setup_tracker(self) -> None:
        """Setup Tracker service."""
        from ordex.rpc.tracker import TxTracker

        self._tracker = TxTracker(
            rpc_client=self._rpc_client,
            block_service=self._blocks,
        )
        logger.debug("Tracker service initialized")

    def _setup_notifications(self) -> None:
        """Setup Notification service."""
        from ordex.rpc.notifications import NotificationService

        self._notifications = NotificationService()
        logger.debug("Notification service initialized")

    @property
    def network(self) -> Any:
        """Get Network Monitor service."""
        self._ensure_initialized()
        return self._network

    @property
    def health(self) -> Any:
        """Get Health Monitor service."""
        self._ensure_initialized()
        return self._health

    @property
    def mempool(self) -> Any:
        """Get Mempool service."""
        self._ensure_initialized()
        return self._mempool

    @property
    def blocks(self) -> Any:
        """Get Block service."""
        self._ensure_initialized()
        return self._blocks

    @property
    def address(self) -> Any:
        """Get Address service."""
        self._ensure_initialized()
        return self._address

    @property
    def transactions(self) -> Any:
        """Get Transaction service."""
        self._ensure_initialized()
        return self._transactions

    @property
    def tracker(self) -> Any:
        """Get Tracker service."""
        self._ensure_initialized()
        return self._tracker

    @property
    def notifications(self) -> Any:
        """Get Notification service."""
        self._ensure_initialized()
        return self._notifications

    @property
    def rpc_client(self) -> Any:
        """Get the primary RPC client."""
        self._ensure_initialized()
        return self._rpc_client

    def _ensure_initialized(self) -> None:
        """Ensure services are initialized."""
        if not self._initialized:
            self.initialize()

    def check_health(self) -> Dict[str, Any]:
        """Get health status of all services.

        Returns:
            Dict with health status of each service
        """
        self._ensure_initialized()

        results = {
            "network": "unknown",
            "health": "unknown",
            "mempool": "unknown",
            "blocks": "unknown",
            "address": "unknown",
            "transactions": "unknown",
            "tracker": "unknown",
            "notifications": "unknown",
        }

        try:
            status = self._health.check()
            results["health"] = status.state.value
        except Exception as e:
            logger.error("Health check failed: %s", e)

        try:
            if self._network:
                healthy = self._network.get_healthy_nodes()
                results["network"] = "healthy" if healthy else "unhealthy"
        except Exception as e:
            logger.error("Network check failed: %s", e)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all services.

        Returns:
            Dict with service statistics
        """
        self._ensure_initialized()

        stats = {
            "tracked_transactions": 0,
            "mempool_size": 0,
            "block_height": 0,
            "cache_stats": {},
        }

        if self._tracker:
            stats["tracked_transactions"] = self._tracker.get_tracked_count()

        if self._mempool:
            mempool_stats = self._mempool.get_stats()
            stats["mempool_size"] = mempool_stats.transaction_count

        if self._blocks:
            tip = self._blocks.get_tip()
            if tip:
                stats["block_height"] = tip.get("height", 0)
            stats["cache_stats"] = self._blocks.get_cache_stats()

        return stats

    def shutdown(self) -> None:
        """Shutdown all services gracefully."""
        logger.info("Shutting down Ordex RPC Services...")
        self._initialized = False


def create_services(
    nodes: List[Dict[str, Any]],
    **kwargs,
) -> OrdexServices:
    """Factory function to create initialized services.

    Args:
        nodes: List of node configurations
        **kwargs: Additional configuration options

    Returns:
        Initialized OrdexServices instance
    """
    config = OrdexConfig(nodes=nodes, **kwargs)
    services = OrdexServices(config)
    services.initialize()
    return services