"""
Ordex RPC CLI Commands.

Provides command-line interface for all RPC operations.
"""

from __future__ import annotations

import argparse
import logging
import sys
import os
from typing import Any, Dict, Optional

from ordex.rpc import OrdexServices, OrdexConfig
from ordex.rpc.config import load_config, get_default_config_path, NETWORK_PORTS
from ordex.rpc.mempool import FeeEstimateMode
from ordex.rpc.address import DerivationPath


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def start_command(args: argparse.Namespace) -> int:
    """Start the RPC server."""
    from ordex.rpc.daemon import run_daemon_loop, run_dual_daemon
    
    setup_logging(args.verbose)
    
    if args.dual:
        print("Starting dual daemon (OrdexCoin + OrdexGold)...")
        run_dual_daemon(oxc_port=args.port, oxg_port=args.oxg_port)
    elif args.network == "all":
        print("Starting all networks (OrdexCoin + OrdexGold)...")
        run_dual_daemon(oxc_port=args.port, oxg_port=args.oxg_port)
    else:
        network = args.network or "ordexcoin"
        port = args.port or NETWORK_PORTS.get(network, {}).get("rpc", 8332)
        print(f"Starting Ordex RPC daemon for {network} on port {port}")
        run_daemon_loop(network, port)

    return 0


def stop_command(args: argparse.Namespace) -> int:
    """Stop the RPC server."""
    print("Stopping Ordex RPC server...")
    print("(Note: In daemon mode, this would stop the running server)")
    return 0


def status_command(args: argparse.Namespace) -> int:
    """Get server status."""
    config = load_config(network=args.network)

    try:
        services = OrdexServices(OrdexConfig(
            nodes=[{"url": f"http://{config.rpc_host}:{config.rpc_port}"}]
        ))
        services.initialize()

        health = services.check_health()
        stats = services.get_stats()

        print(f"Network: {args.network or config.network}")
        print(f"URL: {config.get_node_url()}")
        print(f"Status:")
        for service, status in health.items():
            print(f"  {service}: {status}")
        print(f"Statistics:")
        print(f"  Block height: {stats.get('block_height', 'N/A')}")
        print(f"  Mempool size: {stats.get('mempool_size', 0)}")
        print(f"  Tracked transactions: {stats.get('tracked_transactions', 0)}")

    except Exception as e:
        print(f"Error connecting to node: {e}")
        return 1

    return 0


def getblockchaininfo_command(args: argparse.Namespace) -> int:
    """Get blockchain info."""
    config = load_config(network=args.network)

    try:
        from ordex.rpc.client import RpcClient
        rpc = RpcClient(
            url=config.get_node_url(),
            username=config.rpc_user,
            password=config.rpc_password,
        )
        info = rpc.getblockchaininfo()

        print(f"Chain: {info.get('chain', 'unknown')}")
        print(f"Blocks: {info.get('blocks', 0)}")
        print(f"Headers: {info.get('headers', 0)}")
        print(f"Best block hash: {info.get('bestblockhash', 'unknown')}")
        print(f"Difficulty: {info.get('difficulty', 0):.2f}")
        print(f"Size on disk: {info.get('size_on_disk', 0):,} bytes")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def getblockcount_command(args: argparse.Namespace) -> int:
    """Get block count."""
    config = load_config(network=args.network)

    try:
        from ordex.rpc.client import RpcClient
        rpc = RpcClient(
            url=config.get_node_url(),
            username=config.rpc_user,
            password=config.rpc_password,
        )
        count = rpc.getblockcount()
        print(count)

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def getblock_command(args: argparse.Namespace) -> int:
    """Get block by height or hash."""
    config = load_config(network=args.network)

    try:
        from ordex.rpc.client import RpcClient
        rpc = RpcClient(
            url=config.get_node_url(),
            username=config.rpc_user,
            password=config.rpc_password,
        )

        block_hash = args.block
        if block_hash.isdigit():
            block_hash = rpc.getblockhash(int(block_hash))

        block = rpc.getblock(block_hash, verbosity=args.verbosity)

        if args.verbosity == 0:
            print(block)
        else:
            print(f"Hash: {block.get('hash', 'unknown')}")
            print(f"Height: {block.get('height', 0)}")
            print(f"Time: {block.get('time', 0)}")
            print(f"Transactions: {len(block.get('tx', []))}")
            print(f"Size: {block.get('size', 0)}")
            print(f"Weight: {block.get('weight', 0)}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def getmempoolinfo_command(args: argparse.Namespace) -> int:
    """Get mempool info."""
    config = load_config(network=args.network)

    try:
        from ordex.rpc.client import RpcClient
        rpc = RpcClient(
            url=config.get_node_url(),
            username=config.rpc_user,
            password=config.rpc_password,
        )

        services = OrdexServices(OrdexConfig(
            nodes=[{"url": config.get_node_url()}]
        ))
        services.initialize()

        stats = services.mempool.get_stats()

        print(f"Size: {stats.transaction_count}")
        print(f"Total fees: {stats.size_bytes} bytes")
        print(f"Min fee: {stats.min_fee} sat/vB")
        print(f"Max fee: {stats.max_fee} sat/vB")
        print(f"Avg fee: {stats.avg_fee:.2f} sat/vB")

        if stats.fee_percentiles:
            print(f"Fee percentiles:")
            print(f"  10%: {stats.fee_percentiles[0]:.2f}")
            print(f"  25%: {stats.fee_percentiles[1]:.2f}")
            print(f"  50%: {stats.fee_percentiles[2]:.2f}")
            print(f"  75%: {stats.fee_percentiles[3]:.2f}")
            print(f"  90%: {stats.fee_percentiles[4]:.2f}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def estimatesmartfee_command(args: argparse.Namespace) -> int:
    """Estimate smart fee."""
    config = load_config(network=args.network)

    try:
        from ordex.rpc.client import RpcClient
        rpc = RpcClient(
            url=config.get_node_url(),
            username=config.rpc_user,
            password=config.rpc_password,
        )

        services = OrdexServices(OrdexConfig(
            nodes=[{"url": config.get_node_url()}]
        ))
        services.initialize()

        mode = FeeEstimateMode.ECONOMIC
        if args.half_hour:
            mode = FeeEstimateMode.HALF_HOUR
        elif args.hour:
            mode = FeeEstimateMode.HOUR

        fee = services.mempool.get_fees(mode)

        print(f"Mode: {mode.value}")
        print(f"Feerate: {fee.feerate:.2f} sat/vB")
        print(f"Blocks: {fee.blocks}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def networkinfo_command(args: argparse.Namespace) -> int:
    """Get network info."""
    config = load_config(network=args.network)

    try:
        from ordex.rpc.client import RpcClient
        rpc = RpcClient(
            url=config.get_node_url(),
            username=config.rpc_user,
            password=config.rpc_password,
        )

        info = rpc.getnetworkinfo()

        print(f"Version: {info.get('version', 0)}")
        print(f"Connections: {info.get('connections', 0)}")
        print(f"Subversion: {info.get('subversion', '')}")
        print(f"Protocol version: {info.get('protocolversion', 0)}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def wallet_create_command(args: argparse.Namespace) -> int:
    """Create a wallet."""
    services = OrdexServices()

    try:
        services.initialize()

        wallet_id = args.name or "default"

        if services.address:
            addresses = services.address.generate(wallet_id, count=5)
            print(f"Created wallet: {wallet_id}")
            print(f"First address: {addresses[0]}")

    except Exception as e:
        print(f"Error creating wallet: {e}")
        return 1

    return 0


def wallet_list_command(args: argparse.Namespace) -> int:
    """List wallets."""
    services = OrdexServices()

    try:
        services.initialize()

        print("Wallets:")
        print("  default (active)")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def wallet_getnewaddress_command(args: argparse.Namespace) -> int:
    """Get new address for wallet."""
    services = OrdexServices()

    try:
        services.initialize()

        wallet_id = args.wallet or "default"
        derivation = DerivationPath.BIP84

        if args.legacy:
            derivation = DerivationPath.BIP44
        elif args.p2sh:
            derivation = DerivationPath.BIP49

        addresses = services.address.generate(wallet_id, count=1, derivation=derivation)
        print(addresses[0])

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def wallet_balance_command(args: argparse.Namespace) -> int:
    """Get wallet balance."""
    services = OrdexServices()

    try:
        services.initialize()
        stats = services.get_stats()

        print(f"Balance: {stats.get('balance', 0)} sats")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def wallet_send_command(args: argparse.Namespace) -> int:
    """Send transaction."""
    config = load_config(network=args.network)

    try:
        services = OrdexServices(OrdexConfig(
            nodes=[{"url": config.get_node_url()}]
        ))
        services.initialize()

        from ordex.rpc.transaction import TransactionBuilder

        builder = TransactionBuilder()
        builder.set_fee_rate(args.fee_rate or 10.0)

        print(f"Sending {args.amount} to {args.address}")
        print("(Note: Full transaction signing requires wallet keys)")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="ordex-rpc",
        description="Ordex RPC CLI - Manage OrdexCoin/OrdexGold wallets and blockchain",
    )

    parser.add_argument(
        "--network",
        choices=["ordexcoin", "ordexgold", "all"],
        help="Network to use",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # start command
    start_parser = subparsers.add_parser("start", help="Start RPC server")
    start_parser.add_argument("--network", "-n", choices=["ordexcoin", "ordexgold", "all"],
                              help="Network to run (default: ordexcoin)")
    start_parser.add_argument("--port", type=int, help="Port for primary network")
    start_parser.add_argument("--oxg-port", type=int, help="Port for OrdexGold (dual mode)")
    start_parser.add_argument("--dual", "-d", action="store_true",
                              help="Run both OrdexCoin and OrdexGold in parallel")

    # stop command
    stop_parser = subparsers.add_parser("stop", help="Stop RPC server")

    # status command
    status_parser = subparsers.add_parser("status", help="Get server status")

    # blockchain commands
    subparsers.add_parser("getblockchaininfo", help="Get blockchain info")
    subparsers.add_parser("getblockcount", help="Get block count")

    getblock_parser = subparsers.add_parser("getblock", help="Get block")
    getblock_parser.add_argument("block", help="Block height or hash")
    getblock_parser.add_argument("--verbosity", "-V", type=int, default=1, help="Verbosity level")

    # mempool commands
    subparsers.add_parser("getmempoolinfo", help="Get mempool info")

    estimate_parser = subparsers.add_parser("estimatesmartfee", help="Estimate smart fee")
    estimate_parser.add_argument("--half-hour", action="store_true", help="Half hour target")
    estimate_parser.add_argument("--hour", action="store_true", help="Hour target")

    # network commands
    subparsers.add_parser("getnetworkinfo", help="Get network info")

    # wallet commands
    wallet_parser = subparsers.add_parser("wallet", help="Wallet operations")
    wallet_sub = wallet_parser.add_subparsers(dest="wallet_command")

    wallet_create = wallet_sub.add_parser("create", help="Create wallet")
    wallet_create.add_argument("name", nargs="?", default="default", help="Wallet name")

    wallet_list = wallet_sub.add_parser("list", help="List wallets")

    wallet_addr = wallet_sub.add_parser("getnewaddress", help="Get new address")
    wallet_addr.add_argument("--wallet", "-w", default="default", help="Wallet name")
    wallet_addr.add_argument("--legacy", action="store_true", help="Legacy P2PKH")
    wallet_addr.add_argument("--p2sh", action="store_true", help="P2SH")

    wallet_balance = wallet_sub.add_parser("balance", help="Get balance")
    wallet_balance.add_argument("--wallet", "-w", default="default", help="Wallet name")

    wallet_send = wallet_sub.add_parser("send", help="Send transaction")
    wallet_send.add_argument("--wallet", "-w", default="default", help="Wallet name")
    wallet_send.add_argument("address", help="Destination address")
    wallet_send.add_argument("amount", type=float, help="Amount")
    wallet_send.add_argument("--fee-rate", "-f", type=float, default=10.0, help="Fee rate")

    return parser


def main(argv: list[str] = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    setup_logging(args.verbose if hasattr(args, "verbose") else False)

    commands = {
        "start": start_command,
        "stop": stop_command,
        "status": status_command,
        "getblockchaininfo": getblockchaininfo_command,
        "getblockcount": getblockcount_command,
        "getblock": getblock_command,
        "getmempoolinfo": getmempoolinfo_command,
        "estimatesmartfee": estimatesmartfee_command,
        "getnetworkinfo": networkinfo_command,
        "wallet": handle_wallet_command,
    }

    if args.command == "wallet":
        return handle_wallet_command(args)

    command_func = commands.get(args.command)
    if command_func:
        return command_func(args)

    print(f"Unknown command: {args.command}")
    return 1


def handle_wallet_command(args: argparse.Namespace) -> int:
    """Handle wallet subcommands."""
    if not hasattr(args, "wallet_command") or not args.wallet_command:
        print("wallet: missing subcommand")
        print("Usage: ordex-rpc wallet <create|list|getnewaddress|balance|send>")
        return 1

    commands = {
        "create": wallet_create_command,
        "list": wallet_list_command,
        "getnewaddress": wallet_getnewaddress_command,
        "balance": wallet_balance_command,
        "send": wallet_send_command,
    }

    command_func = commands.get(args.wallet_command)
    if command_func:
        return command_func(args)

    print(f"Unknown wallet command: {args.wallet_command}")
    return 1


if __name__ == "__main__":
    sys.exit(main())