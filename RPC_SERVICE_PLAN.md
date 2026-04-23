# Ordex RPC Service Implementation Plan

## Overview

This plan outlines the RPC services required to build a complete multi-wallet, multi-coin platform supporting web wallets, swap services, liquidity pools, and explorers.

**Current Status:**
- Base library: Complete (v1.0.0 - 368 tests)
- UTXO Service: Implemented on `feat/rpc-service` branch
- Remaining services: To be implemented

---

## Services Architecture

```
ordex/
├── rpc/
│   ├── client.py          # Existing: Basic JSON-RPC client
│   ├── transaction.py     # NEW: Transaction building, signing, broadcasting
│   ├── address.py         # NEW: HD address generation, derivation
│   ├── network.py         # NEW: Multi-node management, health
│   ├── mempool.py         # NEW: Mempool monitoring, fees
│   ├── block.py           # NEW: Block headers, notifications
│   ├── notifications.py   # NEW: Webhooks, callbacks
│   └── services.py        # NEW: Unified service container
├── wallet/
│   ├── utxo.py            # Existing: UTXO management
│   ├── wallet.py          # NEW: High-level wallet service
│   └── signing.py         # Existing: Transaction signing
└── chain/
    └── chainparams.py     # Existing: Chain configurations
```

---

## Service Specifications

### 1. Transaction Service

**File:** `ordex/rpc/transaction.py`

**Purpose:** Build, sign, and broadcast transactions with support for RBF, CPFP, multi-sig, PSBT.

**Features:**
- `TransactionBuilder` class
  - Add inputs/outputs
  - Fee estimation and calculation
  - Change output handling
  - RBF (Replace-By-Fee) support
  - CPFP (Child Pays For Parent) support
- `TransactionBroadcaster`
  - Send raw transactions
  - Track propagation
  - Retry logic
- `TransactionMonitor`
  - Watch pending transactions
  - Confirmation tracking
  - Replace-by-fee initiation

**API:**
```python
class TransactionService:
    def build(self, wallet_id: str, outputs: List[tuple], fee_rate: int) -> CTransaction
    def sign(self, tx: CTransaction, wallet_id: str) -> CTransaction
    def broadcast(self, tx: CTransaction) -> str  # returns txid
    def monitor(self, txid: str, callback: Callable) -> None
    def replace(self, txid: str, new_fee: int) -> str
```

**Tests Required:** 15-20 tests
- Build transaction
- Sign transaction
- Broadcast success/failure
- RBF
- CPFP
- Fee estimation
- Error handling

---

### 2. Address Service

**File:** `ordex/rpc/address.py`

**Purpose:** HD address generation, derivation, batch operations, address validation.

**Features:**
- `AddressService` class
  - Generate receiving addresses
  - Generate change addresses
  - Batch address generation
  - Address validation
  - Gap limit tracking
  - Address discovery (scan for used addresses)
- `HDDeriver` utility
  - BIP44/BIP49/BIP84 derivation paths
  - External/internal chain support
  - Custom derivation paths

**API:**
```python
class AddressService:
    def __init__(self, rpc_client: RpcClient, wallet_manager: WalletManager)
    def generate(self, wallet_id: str, count: int = 1) -> List[str]
    def validate(self, address: str) -> bool
    def discover(self, wallet_id: str, gap_limit: int = 20) -> List[str]
    def get_derivation(self, address: str) -> Dict
    def import_address(self, wallet_id: str, address: str) -> bool
```

**Tests Required:** 15-20 tests
- Generate single/multiple addresses
- Validate addresses (valid/invalid)
- Address formatting
- Gap limit behavior
- Discovery scanning

---

### 3. Network Monitor Service

**File:** `ordex/rpc/network.py`

**Purpose:** Manage multiple RPC connections, health checks, failover.

**Features:**
- `NodePool` class
  - Multiple RPC endpoints
  - Connection health monitoring
  - Automatic failover
  - Load balancing (round-robin, priority)
  - Latency tracking
- `HealthMonitor`
  - Ping/pong checks
  - Block height sync
  - Mempool size monitoring
  - Connection status callbacks
- `NetworkStats`
  - Connected peers count
  - Average latency
  - Block height differences
  - Network fees comparison

**API:**
```python
class NodePool:
    def __init__(self, nodes: List[Dict[str, Any]])
    def get_client(self) -> RpcClient
    def add_node(self, url: str, priority: int = 1)
    def remove_node(self, url: str)
    def get_healthy_nodes(self) -> List[Dict]
    def get_stats(self) -> NetworkStats

class HealthMonitor:
    def start(self, interval: int = 30)
    def stop(self)
    def get_status(self) -> Dict
    def on_unhealthy(self, callback: Callable)
    def on_recovered(self, callback: Callable)
```

**Tests Required:** 15-20 tests
- Node pool failover
- Health check intervals
- Latency tracking
- Automatic reconnection

---

### 4. Mempool Service

**File:** `ordex/rpc/mempool.py`

**Purpose:** Monitor mempool, estimate fees, track unconfirmed transactions.

**Features:**
- `MempoolMonitor` class
  - Get mempool contents
  - Track unconfirmed UTXOs
  - Fee estimation (economic/half-hour/hour)
  - Mempool differences (new/removed)
- `FeeEstimator` (enhanced)
  - Smart fee estimates
  - Custom fee strategies
  - Historical analysis
- `MempoolStats`
  - Size in bytes
  - Transaction count
  - Fee distribution

**API:**
```python
class MempoolService:
    def get_mempool(self) -> List[Dict]
    def get_fees(self, mode: str = "economic") -> FeeEstimate
    def get_utxos(self) -> List[UTXO]
    def track_transaction(self, txid: str) -> None
    def get_transaction(self, txid: str) -> Optional[Dict]
    def on_new_transaction(self, callback: Callable)
    def on_transaction_confirmed(self, callback: Callable)
```

**Tests Required:** 12-15 tests
- Mempool retrieval
- Fee estimation accuracy
- Transaction tracking
- Callbacks

---

### 5. Block Service

**File:** `ordex/rpc/block.py`

**Purpose:** Block headers, verification, subscription notifications.

**Features:**
- `BlockService` class
  - Get block headers
  - Block header verification
  - Block subscription (ZMQ/WebSocket)
  - Reorg handling
- `BlockCache`
  - LRU cache for blocks
  - Invalidation on reorg
- `BlockNotifications`
  - New block callbacks
  - Reorg callbacks
  - Confirmation notifications

**API:**
```python
class BlockService:
    def get_block(self, block_hash: str, verbosity: int = 1) -> Dict
    def get_header(self, height: int) -> CBlockHeader
    def verify_header(self, header: CBlockHeader) -> bool
    def subscribe(self, callback: Callable)
    def unsubscribe(self, subscription_id: str)
    def on_reorg(self, callback: Callable)
    def get_tip(self) -> Dict
```

**Tests Required:** 10-12 tests
- Header retrieval
- Verification
- Caching
- Subscription callbacks

---

### 6. Notification Service

**File:** `ordex/rpc/notifications.py`

**Purpose:** Webhooks, callbacks, event system for all notifications.

**Features:**
- `NotificationService` class
  - Event registration
  - Webhook delivery
  - Retry logic for webhooks
  - Event filtering
- `EventBus`
  - Transaction events
  - Block events
  - Balance change events
  - Address activity events
- `WebhookManager`
  - Configure endpoints
  - HMAC signatures
  - Delivery status

**API:**
```python
class NotificationService:
    def register(self, event: str, callback: Callable)
    def unregister(self, event: str, callback: Callable)
    def emit(self, event: str, data: Dict)
    def add_webhook(self, url: str, events: List[str], secret: str)
    def remove_webhook(self, webhook_id: str)

# Events:
# - wallet.balance_changed
# - wallet.utxo.spent
# - wallet.utxo.created
# - tx.new
# - tx.confirmed
# - tx.replaced
# - block.new
# - block.reorg
```

**Tests Required:** 12-15 tests
- Event registration
- Webhook delivery
- HMAC signatures
- Retry logic

---

### 7. Health Monitor Service

**File:** `ordex/rpc/health.py`

**Purpose:** System health, metrics, alerting.

**Features:**
- `HealthService` class
  - Component health checks
  - Metrics collection
  - Alert callbacks
- `MetricsCollector`
  - Request latencies
  - Error rates
  - Queue sizes
  - Memory usage
- `HealthCheck`
  - RPC connectivity
  - Block sync status
  - Wallet sync status

**API:**
```python
class HealthService:
    def check(self) -> HealthStatus
    def get_metrics(self) -> Dict
    def on_degraded(self, callback: Callable)
    def on_unhealthy(self, callback: Callable)
    def reset_metrics(self)

@dataclass
class HealthStatus:
    healthy: bool
    components: Dict[str, ComponentHealth]
    latency_ms: int
    timestamp: str
```

**Tests Required:** 10-12 tests
- Health checks
- Metrics collection
- Alert callbacks

---

### 8. Transaction Tracker Service

**File:** `ordex/rpc/tracker.py`

**Purpose:** Track pending transactions, confirmation status, wallet balance changes.

**Features:**
- `TxTracker` class
  - Track outgoing transactions
  - Confirmation tracking (0-conf, 1-conf, 6-conf)
  - Balance delta tracking
  - Replace-by-fee tracking
- `WalletTracker`
  - Balance history
  - UTXO changes
  - Transaction history

**API:**
```python
class TxTracker:
    def track(self, txid: str, wallet_id: str, amount: int)
    def get_status(self, txid: str) -> TxStatus
    def get_confirmations(self, txid: str) -> int
    def on_confirmation(self, txid: str, callback: Callable)

class WalletTracker:
    def track_balance(self, wallet_id: str)
    def get_history(self, wallet_id: str, limit: int = 100) -> List[Dict]
    def on_change(self, wallet_id: str, callback: Callable)
```

**Tests Required:** 10-12 tests
- Tracking
- Status retrieval
- Confirmation callbacks

---

## Implementation Order

### Phase 1: Core Infrastructure
1. **Network Monitor** - Foundation for multi-node
2. **Health Monitor** - System health

### Phase 2: Data Services
3. **Mempool Service** - Fee estimation, mempool monitoring
4. **Block Service** - Block data

### Phase 3: Address Management
5. **Address Service** - HD derivation, discovery

### Phase 4: Transaction Flow
6. **Transaction Service** - Build, sign, broadcast
7. **Tx Tracker** - Transaction tracking

### Phase 5: Notifications
8. **Notification Service** - Event system

### Phase 6: Integration
9. **Unified Service Container** - Connect all services

---

## Testing Requirements

| Service | Tests | Coverage Target |
|---------|-------|----------------|
| Transaction Service | 15-20 | 90% |
| Address Service | 15-20 | 90% |
| Network Monitor | 15-20 | 85% |
| Mempool Service | 12-15 | 85% |
| Block Service | 10-12 | 85% |
| Notification Service | 12-15 | 80% |
| Health Monitor | 10-12 | 85% |
| Tx Tracker | 10-12 | 85% |
| **Total** | **99-126** | **85%+** |

---

## Documentation Requirements

Each service requires:
1. **Class docstrings** - Purpose, usage
2. **Method docstrings** - Args, returns, raises
3. **README additions** - Usage examples
4. **API reference** - For Sphinx docs

---

## Dependencies Between Services

```
Network Monitor
    ↓
Health Monitor ← Mempool Service
    ↓               ↓
Address Service ← Transaction Service ← Tx Tracker
    ↓
Block Service
    ↓
Notification Service
```

---

## Estimated Timeline

| Phase | Services | Estimated Time |
|-------|----------|----------------|
| 1 | Network, Health | 2-3 days |
| 2 | Mempool, Block | 2-3 days |
| 3 | Address | 2 days |
| 4 | Transaction, TxTracker | 3-4 days |
| 5 | Notifications | 2 days |
| 6 | Integration | 2-3 days |
| **Total** | | **13-18 days** |

---

## Next Steps

1. Review and approve plan
2. Create branch: `feat/rpc-services`
3. Implement Phase 1 services
4. Write tests and documentation
5. Repeat for subsequent phases
6. Integration testing

---

*Generated: April 2026*