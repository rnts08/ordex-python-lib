# Ordex RPC Documentation

## Overview

Python library for multi-wallet, multi-coin platform supporting OrdexCoin (OXC) and OrdexGold (OXG).

**Important:** This is **NOT a full node**. It connects to existing `bitcoind`/`ordexcoind` nodes via JSON-RPC and provides an enhanced wallet and service layer on top. You need a running full node to use this library.

---

## Two Usage Modes

### 1. Import Library
Import into Python projects to access wallet services, fee estimation, transaction building, etc.

### 2. CLI Daemon
Run as a utility daemon that connects to node RPC - provides wallet commands and blockchain queries.

---

## Installation

```bash
pip install ordex
```

Or from source:

```bash
git clone https://github.com/ordexco/ordex-python-lib
cd ordex-python-lib
pip install -e .
```

---

## Quick Start

### Prerequisites

You need a running OrdexCoin or OrdexGold node with RPC enabled:

```bash
# ordexcoind.conf
rpcuser=rpcuser
rpcpassword=rpcpass
rpcport=8332
server=1
```

### As Python Library

```python
from ordex.rpc import OrdexServices, create_services

# Initialize with node config
services = create_services([{
    "url": "http://localhost:8332",
    "user": "rpcuser",
    "password": "rpcpass"
}])

# Use services
fees = services.mempool.get_fees()
tip = services.blocks.get_tip()
print(f"Block height: {tip.get('height')}")
```

### As CLI Daemon

```bash
# Start server for OrdexCoin
ordex-rpc start --network ordexcoin

# Start server for OrdexGold
ordex-rpc start --network ordexgold

# Run both networks in parallel (dual mode)
ordex-rpc start --dual
```

---

## Architecture

### Not a Full Node

```
┌─────────────────┐          ┌─────────────────────┐
│  Your Service   │  ────►  │  Ordex RPC Library  │
└─────────────────┘          └──────────┬──────────┘
                                         │ RPC
                                         ▼
                              ┌─────────────────────┐
                              │  bitcoind/ordexcoind │
                              │  (Full Node Required) │
                              └─────────────────────┘
```

The library provides:
- **Enhanced wallet features** on top of node RPC
- **Multi-wallet management** with HD derivation
- **Fee estimation** with smart strategies
- **Transaction tracking** and confirmation callbacks
- **Event notifications** via webhooks

The full node provides:
- Blockchain data (blocks, transactions)
- Mempool access
- Transaction broadcasting
- UTXO management

---

## Networks

### OrdexCoin (OXC)
- **Symbol:** OXC
- **Algorithm:** SHA-256d PoW
- **Block Time:** ~10 minutes
- **Supply:** 8,450,000 OXC
- **Default Ports:** 8332 (RPC), 8333 (P2P)
- **Chain ID:** 86000

### OrdexGold (OXG)
- **Symbol:** OXG
- **Algorithm:** Scrypt PoW
- **Block Time:** ~2.5 minutes
- **Supply:** 1,001,000 OXG
- **Default Ports:** 19332 (RPC), 19333 (P2P)
- **Chain ID:** 86001

---

## RPC Services

### Service Architecture

```
ordex/rpc/                    # RPC Service Layer
├── network.py              # Multi-node management, failover
├── health.py              # Health monitoring, metrics
├── mempool.py            # Mempool & fee estimation
├── block.py             # Block data retrieval, caching
├── address.py          # HD address generation, validation
├── transaction.py     # Transaction building, signing
├── tracker.py        # Transaction tracking, confirmations
├── notifications.py  # Webhooks, event system
├── client.py        # Base JSON-RPC client
├── services.py     # Unified service container
├── daemon.py      # Background daemon management
└── config.py     # Configuration management

ordex/wallet/              # Base Wallet Layer
├── utxo.py              # Wallet, UTXO management
└── signing.py           # Transaction signing

ordex/chain/              # Chain Configuration
└── chainparams.py       # Network parameters (OXC/OXG)
```

### Services Explained

| Service | Purpose | Depends On |
|---------|---------|------------|
| Network | Multi-node RPC, failover | None |
| Health | System health, metrics | Network |
| Mempool | Fee estimation, mempool | Network |
| Block | Block data, headers | Network |
| Address | HD derivation, validation | Mempool |
| Transaction | Build/sign/broadcast | Network, Address |
| Tracker | Track txs, confirmations | Block |
| Notifications | Events, webhooks | All services |

---

## Usage Examples

### Network Service

```python
from ordex.rpc.network import NodePool, LoadBalancingStrategy

pool = NodePool(nodes=[
    {"url": "http://primary:8332", "priority": 1},
    {"url": "http://backup:8332", "priority": 2},
])
pool.set_strategy(LoadBalancingStrategy.LATENCY)

client = pool.get_client()
```

### Health Monitoring

```python
from ordex.rpc.health import HealthMonitor, ComponentType

monitor = HealthMonitor(check_interval=30)
monitor.register_component("primary-node", ComponentType.RPC)

status = monitor.check()
if not status.healthy:
    print(f"System degraded: {status.message}")

summary = monitor.get_metrics_summary("rpc_latency")
print(f"P95: {summary.p95_latency_ms}ms")
```

### Mempool & Fees

```python
from ordex.rpc.mempool import MempoolService, FeeEstimateMode

mempool = MempoolService(rpc_client=client)

fees = mempool.get_fees(FeeEstimateMode.ECONOMIC)
print(f"Fee: {fees.feerate} sat/vB")

stats = mempool.get_stats()
print(f"Mempool: {stats.transaction_count} txs")
```

### Block Data

```python
from ordex.rpc.block import BlockService

blocks = BlockService(rpc_client=client)

tip = blocks.get_tip()
print(f"Height: {tip.get('height')}, Hash: {tip.get('hash')}")

blocks.on_new_block(lambda header: print(f"New block: {header.height}"))
```

### Address Management

```python
from ordex.rpc.address import AddressService, DerivationPath, ChainType

address_svc = AddressService(rpc_client=client)

addresses = address_svc.generate("wallet1", count=10, derivation=DerivationPath.BIP84)
print(addresses)

if address_svc.validate("bc1q..."):
    print("Valid")
```

### Transaction Service

```python
from ordex.rpc.transaction import TransactionService, TransactionBuilder

tx_svc = TransactionService(rpc_client=client)
builder = TransactionBuilder()

builder.set_fee_rate(15.0)
builder.add_input("prev_txid", 0, 100000)
builder.add_output("dest_addr", 80000)

tx = builder.build()
tx = tx_svc.sign(tx, "wallet_id")
result = tx_svc.broadcast(tx)

print(f"TXID: {result.txid}")
```

### Transaction Tracking

```python
from ordex.rpc.tracker import TxTracker

tracker = TxTracker(rpc_client=client)

tracker.track("txid", "wallet1", 50000, fee=1000)

confirmations = tracker.get_confirmations("txid")
print(f"Confirmations: {confirmations}")

tracker.on_confirmation(lambda txid, info: print(f"Confirmed: {txid}"))
```

### Notifications

```python
from ordex.rpc.notifications import NotificationService, EventType

notifs = NotificationService()

notifs.register(EventType.TX_NEW.value, lambda e: print(f"New tx: {e.data}"))

notifs.add_webhook(
    "https://my-server.com/webhook",
    events=["tx.new", "tx.confirmed"],
    secret="hmac-secret"
)
```

---

## Unified Services Container

```python
from ordex.rpc import OrdexServices, OrdexConfig

config = OrdexConfig(
    nodes=[
        {"url": "http://localhost:8332", "priority": 1},
    ],
    check_interval=30,
    gap_limit=20,
)

services = OrdexServices(config)
services.initialize()

mempool = services.mempool
blocks = services.blocks
transactions = services.transactions
tracker = services.tracker

health = services.check_health()
stats = services.get_stats()
print(stats)
```

---

## CLI Daemon Usage

### Start Server

```bash
# OrdexCoin only
ordex-rpc start --network ordexcoin

# OrdexGold only
ordex-rpc start --network ordexgold --port 19332

# Both networks in parallel
ordex-rpc start --dual
ordex-rpc start --network all

# Custom ports for dual mode
ordex-rpc start --dual --port 9032 --oxg-port 19332
```

### Wallet Commands

```bash
ordex-rpc wallet create my_wallet
ordex-rpc wallet list
ordex-rpc wallet getnewaddress --wallet my_wallet
ordex-rpc wallet balance --wallet my_wallet
ordex-rpc wallet send --wallet my_wallet --address <addr> --amount 1.0
```

### Blockchain Commands

```bash
ordex-rpc getblockchaininfo
ordex-rpc getblockcount
ordex-rpc getblock 100000
ordex-rpc getmempoolinfo
ordex-rpc estimatesmartfee --half-hour
```

### Network Commands

```bash
ordex-rpc getnetworkinfo
ordex-rpc getpeerinfo
```

---

## Configuration

### Environment Variables

```bash
export OXR_RPC_NETWORK=ordexcoin
export OXR_RPC_USER=rpcuser
export OXR_RPC_PASSWORD=rpcpass
export OXR_DATA_DIR=~/.ordex
export OXR_LOG_LEVEL=INFO
```

### Config File (~/.ordex/ordex.conf)

```ini
[ordexcoin]
rpcconnect=127.0.0.1
rpcport=8332
rpcuser=rpcuser
rpcpassword=rpcpass

[ordexgold]
rpcconnect=127.0.0.1
rpcport=19332
rpcuser=rpcuser
rpcpassword=rpcpass
```

---

## Testing

```bash
python -m pytest
python -m pytest tests/test_network.py -v
python -m pytest --cov=ordex --cov-report=html
```

---

## Version History

### v1.1.1 (April 2026)
- Dual network daemon support
- `ordex-rpc start --dual` for parallel OXC/OXG
- Daemon manager for multiple networks

### v1.1.0 (April 2026)
- 8 RPC services + unified container
- 598 total tests
- Network Monitor, Health Monitor, Mempool, Block, Address, Transaction services
- Tx Tracker, Notification Service
- CLI daemon

### v1.0.0
- Base library
- UTXO management, Transaction signing
- 368 tests

---

## License

See LICENSE.md for non-commercial use terms.