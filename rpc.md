# Ordex RPC Documentation

## Overview

Python library for multi-wallet, multi-coin platform supporting OrdexCoin (OXC) and OrdexGold (OXG). Can be used as:

1. **Import library** - Import into Python projects
2. **CLI daemon** - Run as standalone RPC server like bitcoind/ordexcoind

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
print(f"Block height: {tip.height}")
```

### As CLI Daemon

```bash
# Start RPC server for OrdexCoin
ordex-rpc --network ordexcoin --port 8332

# Start RPC server for OrdexGold  
ordex-rpc --network ordexgold --port 19332

# Start with both networks
ordex-rpc --network all --port 8332
```

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
ordex/
├── rpc/                      # RPC Services
│   ├── network.py           # Multi-node management
│   ├── health.py          # Health monitoring
│   ├── mempool.py        # Mempool & fees
│   ├── block.py         # Block data
│   ├── address.py       # HD addresses
│   ├── transaction.py  # Build/sign/broadcast
│   ├── tracker.py     # Tx tracking
│   ├── notifications.py # Events & webhooks
│   ├── client.py     # Base RPC client
│   └── services.py   # Unified container
├── wallet/
│   ├── utxo.py       # Wallet & UTXO management
│   └── signing.py    # Transaction signing
└── chain/
    └── chainparams.py # Network parameters
```

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

# Get metrics
summary = monitor.get_metrics_summary("rpc_latency")
print(f"P95: {summary.p95_latency_ms}ms")
```

### Mempool & Fees

```python
from ordex.rpc.mempool import MempoolService, FeeEstimateMode

mempool = MempoolService(rpc_client=client)

# Get fee estimates
fees = mempool.get_fees(FeeEstimateMode.ECONOMIC)
print(f"Fee: {fees.feerate} sat/vB")

# Monitor mempool
stats = mempool.get_stats()
print(f"Mempool: {stats.transaction_count} txs")
```

### Block Data

```python
from ordex.rpc.block import BlockService

blocks = BlockService(rpc_client=client)

# Get latest block
tip = blocks.get_tip()
print(f"Height: {tip.height}, Hash: {tip.hash}")

# Subscribe to new blocks
blocks.on_new_block(lambda header: print(f"New block: {header.height}"))
```

### Address Management

```python
from ordex.rpc.address import AddressService, DerivationPath, ChainType

address_svc = AddressService(rpc_client=client)

# Generate BIP84 addresses
addresses = address_svc.generate("wallet1", count=10, derivation=DerivationPath.BIP84)
print(addresses)

# Validate address
if address_svc.validate("bc1q..."):
    print("Valid")
```

### Transaction Service

```python
from ordex.rpc.transaction import TransactionService, TransactionBuilder

tx_svc = TransactionService(rpc_client=client)
builder = TransactionBuilder()

# Build transaction
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

# Track transaction
tracker.track("txid", "wallet1", 50000, fee=1000)

# Get confirmations
confirmations = tracker.get_confirmations("txid")
print(f"Confirmations: {confirmations}")

# Callback on confirmation
tracker.on_confirmation(lambda txid, info: print(f"Confirmed: {txid}"))
```

### Notifications

```python
from ordex.rpc.notifications import NotificationService, EventType

notifs = NotificationService()

# Register event handler
notifs.register(EventType.TX_NEW.value, lambda e: print(f"New tx: {e.data}"))

# Or add webhook
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

# All services available via properties
mempool = services.mempool
blocks = services.blocks
transactions = services.transactions
tracker = services.tracker

# Health check
health = services.check_health()

# Statistics
stats = services.get_stats()
print(stats)
```

---

## CLI Daemon Usage

### Start RPC Server

```bash
# OrdexCoin on default port
ordex-rpc start --network ordexcoin

# OrdexGold with custom port
ordex-rpc start --network ordexgold --port 19332

# Both networks
ordex-rpc start --network all
```

### Wallet Commands

```bash
# Create wallet
ordex-rpc wallet create my_wallet

# List wallets
ordex-rpc wallet list

# Get new address
ordex-rpc wallet getnewaddress --wallet my_wallet

# Get balance
ordex-rpc wallet balance --wallet my_wallet

# Send transaction
ordex-rpc wallet send --wallet my_wallet --address <addr> --amount 1.0
```

### Blockchain Commands

```python
# Get blockchain info
ordex-rpc getblockchaininfo

# Get block count
ordex-rpc getblockcount

# Get block by height
ordex-rpc getblock 100000

# Get mempool info
ordex-rpc getmempoolinfo

# Get fee estimates
ordex-rpc estimatesmartfee 6
```

### Network Commands

```bash
# Get network info
ordex-rpc getnetworkinfo

# Get peer info
ordex-rpc getpeerinfo

# Add node
ordex-rpc addnode "10.0.0.1:8333" add
```

---

## Configuration

### Environment Variables

```bash
# Default network
export OXR_RPC_NETWORK=ordexcoin

# RPC credentials
export OXR_RPC_USER=rpcuser
export OXR_RPC_PASSWORD=rpcpass

# Data directory
export OXR_DATA_DIR=~/.ordex

# Log level
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
# Run all tests
python -m pytest

# Run specific service tests
python -m pytest tests/test_network.py -v

# Coverage report
python -m pytest --cov=ordex --cov-report=html
```

---

## Version History

### v1.1.0 (April 2026)
- Added 8 RPC services + unified container
- 598 total tests
- Network Monitor with failover
- Health Monitor with metrics
- Mempool, Block, Address, Transaction services
- Tx Tracker, Notification Service
- CLI daemon

### v1.0.0
- Base library
- UTXO management
- Transaction signing
- 368 tests

---

## License

MIT License