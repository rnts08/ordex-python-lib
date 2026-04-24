"""
Ordex RPC Configuration.

Manages configuration from files, environment variables, and CLI arguments.
"""

from __future__ import annotations

import os
import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


NETWORK_PORTS = {
    "ordexcoin": {"rpc": 8332, "p2p": 8333},
    "ordexgold": {"rpc": 19332, "p2p": 19333},
}

NETWORK_CHAIN_IDS = {
    "ordexcoin": 86000,
    "ordexgold": 86001,
}


@dataclass
class NodeConfig:
    """Configuration for a single node."""
    url: str = "http://127.0.0.1:8332"
    user: str = "rpcuser"
    password: str = "rpcpass"
    priority: int = 1


@dataclass
class NetworkConfig:
    """Configuration for a network."""
    name: str = "ordexcoin"
    rpc_port: int = 8332
    p2p_port: int = 8333
    chain_id: int = 86000
    nodes: List[NodeConfig] = field(default_factory=list)


@dataclass 
class OrdexRPCConfig:
    """Main RPC daemon configuration."""
    network: str = "ordexcoin"
    rpc_host: str = "127.0.0.1"
    rpc_port: int = 8332
    rpc_user: str = "rpcuser"
    rpc_password: str = "rpcpass"
    datadir: Path = field(default_factory=lambda: Path.home() / ".ordex")
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    daemon: bool = False
    verbose: bool = False
    pid_file: Optional[Path] = None
    networks: Dict[str, NetworkConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rpc_port is None:
            self.rpc_port = NETWORK_PORTS.get(self.network, {}).get("rpc", 8332)

    @classmethod
    def from_file(cls, path: Path) -> OrdexRPCConfig:
        """Load configuration from file."""
        config = cls()
        parser = configparser.ConfigParser()

        if path.exists():
            parser.read(path)

        if "default" in parser:
            default_section = parser["default"]
            config.network = default_section.get("network", "ordexcoin")
            config.datadir = Path(default_section.get("datadir", str(config.datadir)))

        if config.network in parser:
            net_section = parser[config.network]
            config.rpc_host = net_section.get("rpcconnect", config.rpc_host)
            config.rpc_port = int(net_section.get("rpcport", str(config.rpc_port)))
            config.rpc_user = net_section.get("rpcuser", config.rpc_user)
            config.rpc_password = net_section.get("rpcpassword", config.rpc_password)

        return config

    @classmethod
    def from_env(cls) -> OrdexRPCConfig:
        """Load configuration from environment variables."""
        config = cls()

        config.network = os.environ.get("OXR_RPC_NETWORK", config.network)
        config.rpc_user = os.environ.get("OXR_RPC_USER", config.rpc_user)
        config.rpc_password = os.environ.get("OXR_RPC_PASSWORD", config.rpc_password)

        if "OXR_DATA_DIR" in os.environ:
            config.datadir = Path(os.environ["OXR_DATA_DIR"])

        config.log_level = os.environ.get("OXR_LOG_LEVEL", config.log_level)

        return config

    def save(self, path: Path) -> None:
        """Save configuration to file."""
        parser = configparser.ConfigParser()

        parser["default"] = {
            "network": self.network,
            "datadir": str(self.datadir),
            "logfile": str(self.log_file or ""),
        }

        parser[self.network] = {
            "rpcconnect": self.rpc_host,
            "rpcport": str(self.rpc_port),
            "rpcuser": self.rpc_user,
            "rpcpassword": self.rpc_password,
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            parser.write(f)

    def get_node_url(self) -> str:
        """Get full RPC URL."""
        return f"http://{self.rpc_host}:{self.rpc_port}"


def get_default_config_path() -> Path:
    """Get default config file path."""
    return Path.home() / ".ordex" / "ordex.conf"


def load_config(
    config_file: Optional[Path] = None,
    network: Optional[str] = None,
) -> OrdexRPCConfig:
    """Load configuration from file, env, or defaults."""
    if config_file is None:
        config_file = get_default_config_path()

    if config_file and config_file.exists():
        config = OrdexRPCConfig.from_file(config_file)
    else:
        config = OrdexRPCConfig.from_env()

    if network:
        config.network = network

    config.rpc_port = NETWORK_PORTS.get(config.network, {}).get("rpc", 8332)

    return config