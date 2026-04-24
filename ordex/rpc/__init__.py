"""
Ordex RPC Services - Unified service container and exports.

This module provides:
- OrdexServices: Unified container for all RPC services
- OrdexConfig: Configuration for services
- create_services(): Factory function to create initialized services

Usage:
    from ordex.rpc import OrdexServices

    services = OrdexServices(config={"nodes": [...]})
    fees = services.mempool.get_fees()
    tip = services.blocks.get_tip()
"""

from ordex.rpc.services import (
    OrdexServices,
    OrdexConfig,
    create_services,
)

from ordex.rpc.client import RpcClient

from ordex.rpc.config import (
    load_config,
    get_default_config_path,
    NETWORK_PORTS,
    NodeConfig,
    NetworkConfig,
    OrdexRPCConfig,
)

__all__ = [
    "OrdexServices",
    "OrdexConfig",
    "create_services",
    "RpcClient",
    "load_config",
    "get_default_config_path",
    "NETWORK_PORTS",
    "NodeConfig",
    "NetworkConfig",
    "OrdexRPCConfig",
]

__version__ = "1.1.0"