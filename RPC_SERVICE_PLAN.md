# Ordex RPC Services - Release v1.1.0

## Overview

RPC Services for multi-wallet, multi-coin platform with support for web wallets, swap services, liquidity pools, and blockchain explorers.

**Version:** 1.1.0  
**Release Date:** April 2026  
**Branch:** `feat/rpc-service` (to be merged)

---

## Architecture

```
ordex/
├── rpc/                     # RPC Services (v1.1.0)
│   ├── network.py           # Network Monitor Service
│   ├── health.py           # Health Monitor Service
│   ├── mempool.py         # Mempool Service
│   ├── block.py           # Block Service
│   ├── address.py        # Address Service
│   ├── transaction.py   # Transaction Service
│   ├── tracker.py      # Tx Tracker Service
│   ├── notifications.py # Notification Service
│   ├── client.py      # Basic JSON-RPC client (base)
│   └── __init__.py   # Service exports
├── wallet/
│   ├── utxo.py        # UTXO Management (base library)
│   └── signing.py     # Transaction signing (base library)
└── chain/
    └── chainparams.py # Chain configurations (base library)
```

---

## Service Overview

### Network Monitor (`network.py`)
Multi-node management with health checks, automatic failover, and load balancing.

**Features:**
- `NodePool`: Multiple RPC endpoints with connection health monitoring
- Automatic failover on node failure
- Load balancing: round-robin, priority, latency, random
- Ping/pong health checks

**API:**
```python
from ordex.rpc.network import NodePool, NetworkStats

pool = NodePool(nodes=[{"url": "http://localhost:8332", "priority": 1}])
client = pool.get_client()
stats = pool.get_stats()
```

---

### Health Monitor (`health.py`)
Component health checks, metrics collection, and alerting.

**Features:**
- Component health tracking
- Metrics collection (requests, latency, errors)
- Percentile calculations (P95, P99)
- Alert callbacks on state changes

**API:**
```python
from ordex.rpc.health import HealthMonitor, HealthState, ComponentType

monitor = HealthMonitor(check_interval=30)
monitor.register_component("rpc-node", ComponentType.RPC)
status = monitor.check()
```

---

### Mempool Service (`mempool.py`)
Mempool monitoring and fee estimation.

**Features:**
- Get mempool contents with caching
- Fee estimation (economic/half-hour/hour targets)
- Unconfirmed UTXO tracking
- Transaction tracking with callbacks

**API:**
```python
from ordex.rpc.mempool import MempoolService, FeeEstimateMode

service = MempoolService(rpc_client=client)
mempool = service.get_mempool()
fees = service.get_fees(FeeEstimateMode.ECONOMIC)
```

---

### Block Service (`block.py`)
Block data retrieval, headers, and notifications.

**Features:**
- Block/header retrieval with LRU caching
- Header verification
- New block subscriptions
- Reorg detection and handling

**API:**
```python
from ordex.rpc.block import BlockService

service = BlockService(rpc_client=client)
header = service.get_header(100)
tip = service.get_tip()
```

---

### Address Service (`address.py`)
HD address generation, validation, and discovery.

**Features:**
- HD address generation (BIP44/BIP49/BIP84)
- Address validation
- Gap limit tracking
- Address discovery scanning
- Batch operations

**API:**
```python
from ordex.rpc.address import AddressService, DerivationPath, ChainType

service = AddressService(rpc_client=client)
addresses = service.generate("wallet1", count=10, derivation=DerivationPath.BIP84)
service.validate("bc1q...")
```

---

### Transaction Service (`transaction.py`)
Transaction building, signing, and broadcasting.

**Features:**
- `TransactionBuilder`: Add inputs/outputs, fee calculation
- `TransactionBroadcaster`: Broadcast with retry logic
- RBF (Replace-By-Fee) support
- Confirmation monitoring

**API:**
```python
from ordex.rpc.transaction import TransactionService, TransactionBuilder

service = TransactionService(rpc_client=client)
builder = TransactionBuilder().set_fee_rate(10.0)
builder.add_input("txid", 0, 100000).add_output("addr", 90000)
tx = builder.build()
result = service.broadcast(tx)
```

---

### Tx Tracker (`tracker.py`)
Transaction tracking for confirmations and balance changes.

**Features:**
- Track outgoing transactions
- Confirmation levels (0-conf, 1-conf, 6-conf)
- RBF tracking
- Wallet balance tracking
- Callbacks for each confirmation level

**API:**
```python
from ordex.rpc.tracker import TxTracker, WalletTracker

tracker = TxTracker(rpc_client=client)
tracker.track("txid", "wallet1", 100000, fee=1000)
tracker.on_confirmation(lambda txid, info: print(f"Confirmed: {txid}"))
```

---

### Notification Service (`notifications.py`)
Event system for webhooks and callbacks.

**Features:**
- Event registration and dispatching
- Webhook delivery with HMAC signatures
- Retry logic for failed webhooks
- Event filtering

**API:**
```python
from ordex.rpc.notifications import NotificationService, EventType

service = NotificationService()
service.register(EventType.TX_NEW.value, lambda e: handle_new_tx(e))
service.emit(EventType.TX_NEW.value, {"txid": "..."})
```

---

## Base Library Services

The following are part of the base ordex library (v1.0.0+):

| Service | File | Purpose |
|--------|------|---------|
| UTXO Management | `ordex/wallet/utxo.py` | Wallet, UTXO selection, persistence |
| Transaction Signing | `ordex/wallet/sign.py` | Bitcoin transaction signing |
| JSON-RPC Client | `ordex/rpc/client.py` | Basic RPC communication |
| Chain Parameters | `ordex/chain/chainparams.py` | Network configurations |

---

## How Services Work Together

```
┌─────────────────────────────────────────────────────────────────┐
│                    RPC Services (v1.1.0)                     │
├─────────────────────────────────────────────────────────────────┤
│  NetworkMonitor ──► HealthMonitor ──► MempoolService          │
│        │             │                │                        │
│        ▼             ▼                ▼                        │
│  AddressService ◄─── TransactionService                 │
│        │                       │                         │
│        ▼                       ▼                         │
│  TxTracker ◄──────── NotificationService                │
│        │                       │                         │
│        ▼                       ▼                         │
│  WalletTracker ────────── BlockService                │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
         Base Library (v1.0.0+)
```

**Service Dependencies:**
1. **Network Monitor** - Foundation for all RPC communication
2. **Health Monitor** - System health, metrics (depends on Network Monitor)
3. **Mempool Service** - Fee estimation (uses Network Monitor)
4. **Block Service** - Block data (uses Network Monitor)
5. **Address Service** - Address management (uses Mempool, Wallet)
6. **Transaction Service** - Build/broadcast (uses Network, Wallet)
7. **Tx Tracker** - Tracking (uses Block Service)
8. **Notification Service** - Events (standalone)

---

## Running RPC Services

### Quick Start

```python
from ordex.rpc import (
    NodePool,
    HealthMonitor,
    MempoolService,
    BlockService,
    AddressService,
    TransactionService,
    TxTracker,
    NotificationService,
)

# 1. Setup network
pool = NodePool(nodes=[
    {"url": "http://localhost:8332", "user": "user", "password": "pass"},
    {"url": "http://backup:8332", "priority": 2},
])

# 2. Initialize services
health = HealthMonitor(check_interval=30)
mempool = MempoolService(rpc_client=pool.get_client())
blocks = BlockService(rpc_client=pool.get_client())
transactions = TransactionService(rpc_client=pool.get_client())
tracker = TxTracker(rpc_client=pool.get_client())
notifications = NotificationService()

# 3. Register handlers
health.register_component("main-node", ComponentType.RPC)
notifications.register("tx.new", lambda e: print(f"New transaction: {e.data}"))

# 4. Use services
fees = mempool.get_fees()
tip = blocks.get_tip()
```

### Example: Send a Transaction

```python
from ordex.rpc import TransactionService, TransactionBuilder, DerivationPath, ChainType
from ordex.rpc.address import AddressService
from ordex.wallet.utxo import WalletManager

# Setup
wallet_mgr = WalletManager()
address_svc = AddressService()
tx_svc = TransactionService(rpc_client=pool.get_client())

# Create wallet and get address
wallet_id = wallet_mgr.create_wallet("my_wallet")
addresses = address_svc.generate(wallet_id, count=5, derivation=DerivationPath.BIP84)

# Build transaction
builder = TransactionBuilder()
builder.set_fee_rate(15.0)  # 15 sat/vB
builder.add_input("prev_txid", 0, 50000)  # UTXO
builder.add_output(addresses[0], 40000)  # Send 40k sats

# Sign and broadcast
tx = builder.build()
tx = tx_svc.sign(tx, wallet_id)
result = tx_svc.broadcast(tx)

if result.success:
    tx_svc.monitor(result.txid, lambda conf: print(f"Confirmations: {conf}"))
```

---

## Testing

```bash
# Run all tests
python -m pytest

# Run RPC service tests only
python -m pytest tests/test_network.py tests/test_health.py \
    tests/test_mempool.py tests/test_block.py tests/test_address.py \
    tests/test_transaction.py tests/test_tracker.py tests/test_notifications.py

# Coverage
python -m pytest --cov=ordex.rpc --cov-report=html
```

---

## Changelog

### v1.1.0 (April 2026)
- Added 8 new RPC services
- 577 total tests (209 new RPC tests)
- Network Monitor with multi-node failover
- Health Monitor with metrics
- Mempool Service with fee estimation
- Block Service with caching
- Address Service with HD derivation
- Transaction Service with RBF/CFPF
- Tx Tracker with confirmation tracking
- Notification Service with webhooks

### v1.0.0 (Previous)
- Base library release
- UTXO management
- Transaction signing
- JSON-RPC client
- 368 tests

---

## License

MIT License - See LICENSE file