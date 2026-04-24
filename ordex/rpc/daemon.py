"""
Ordex RPC Daemon.

Runs RPC services as a background process, optionally for multiple networks.
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ordex.rpc import OrdexServices, OrdexConfig
from ordex.rpc.config import NETWORK_PORTS

logger = logging.getLogger(__name__)


@dataclass
class NetworkDaemon:
    """Daemon process for a single network."""
    network: str
    port: int
    services: Optional[OrdexServices] = None
    running: bool = False


class DaemonManager:
    """Manages multiple network daemons."""
    
    def __init__(self) -> None:
        self._daemons: Dict[str, NetworkDaemon] = {}
        self._shutdown_flag = False
    
    def start(self, network: str, port: Optional[int] = None) -> NetworkDaemon:
        """Start a daemon for a network."""
        if network in self._daemons and self._daemons[network].running:
            raise ValueError(f"Daemon for {network} already running")
        
        rpc_port = port or NETWORK_PORTS.get(network, {}).get("rpc", 8332)
        
        daemon = NetworkDaemon(
            network=network,
            port=rpc_port,
        )
        
        config = OrdexConfig(
            nodes=[{
                "url": f"http://127.0.0.1:{rpc_port}",
                "priority": 1,
            }]
        )
        
        daemon.services = OrdexServices(config)
        daemon.services.initialize()
        daemon.running = True
        
        self._daemons[network] = daemon
        logger.info(f"Started daemon for {network} on port {rpc_port}")
        
        return daemon
    
    def stop(self, network: str) -> bool:
        """Stop a daemon."""
        if network not in self._daemons:
            return False
        
        daemon = self._daemons[network]
        if daemon.services:
            daemon.services.shutdown()
        daemon.running = False
        del self._daemons[network]
        
        logger.info(f"Stopped daemon for {network}")
        return True
    
    def stop_all(self) -> None:
        """Stop all daemons."""
        for network in list(self._daemons.keys()):
            self.stop(network)
    
    def get_status(self) -> Dict[str, Dict]:
        """Get status of all daemons."""
        status = {}
        for network, daemon in self._daemons.items():
            info = {
                "running": daemon.running,
                "port": daemon.port,
            }
            if daemon.services:
                try:
                    health = daemon.services.check_health()
                    stats = daemon.services.get_stats()
                    info["health"] = health
                    info["stats"] = stats
                except Exception as e:
                    info["error"] = str(e)
            status[network] = info
        return status
    
    @property
    def networks(self) -> List[str]:
        """Get list of running networks."""
        return list(self._daemons.keys())


_daemon_manager: Optional[DaemonManager] = None


def get_daemon_manager() -> DaemonManager:
    """Get the global daemon manager."""
    global _daemon_manager
    if _daemon_manager is None:
        _daemon_manager = DaemonManager()
    return _daemon_manager


def start_daemon(
    network: str,
    port: Optional[int] = None,
    daemon_mode: bool = False,
) -> NetworkDaemon:
    """Start a daemon for a network."""
    manager = get_daemon_manager()
    return manager.start(network, port)


def stop_daemon(network: str) -> bool:
    """Stop a daemon for a network."""
    manager = get_daemon_manager()
    return manager.stop(network)


def stop_all_daemons() -> None:
    """Stop all running daemons."""
    manager = get_daemon_manager()
    manager.stop_all()


def run_daemon_loop(network: str, port: Optional[int] = None) -> None:
    """Run daemon in foreground loop."""
    manager = get_daemon_manager()
    daemon = manager.start(network, port)
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        manager.stop(network)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info(f"Daemon running for {network}. Press Ctrl+C to stop.")
    
    try:
        while daemon.running:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop(network)


def run_dual_daemon(
    oxc_port: Optional[int] = None,
    oxg_port: Optional[int] = None,
) -> None:
    """Run daemons for both networks."""
    manager = get_daemon_manager()
    
    def signal_handler(signum, frame):
        logger.info("Received signal, shutting down...")
        manager.stop_all()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if oxc_port or oxg_port:
            if oxc_port:
                manager.start("ordexcoin", oxc_port)
            if oxg_port:
                manager.start("ordexgold", oxg_port)
        else:
            oxc_port = NETWORK_PORTS.get("ordexcoin", {}).get("rpc", 8332)
            oxg_port = NETWORK_PORTS.get("ordexgold", {}).get("rpc", 19332)
            manager.start("ordexcoin", oxc_port)
            manager.start("ordexgold", oxg_port)
        
        logger.info(f"Running dual daemon. Networks: {manager.networks}")
        logger.info("Press Ctrl+C to stop.")
        
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()