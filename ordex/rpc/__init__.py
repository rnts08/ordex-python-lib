"""
Ordex RPC Services - Unified service container and exports.

This module provides:
- OrdexServices: Unified container for all RPC services
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

__all__ = [
    "OrdexServices",
    "OrdexConfig", 
    "create_services",
]

__version__ = "1.1.0"