# Ideas - Building Services on Ordex

This document maps out how the Ordex RPC library can be used to build higher-level services like wallets, swap services, blockchain explorers, and more.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Higher-Level Services                      │
│  (Wallets, Swap Services, Explorers, Liquidity Pools)       │
├─────────────────────────────────────────────────────────────┤
│                    Ordex RPC Library                        │
│  (Network, Health, Mempool, Block, Address, Tx, Tracker)    │
├───��─────────────────────────────────────────────────────────┤
│                    Ordex Base Library                       │
│  (UTXO, Signing, Chain Params, Primitives)                   │
├─────────────────────────────────────────────────────────────┤
│                    Full Node RPC                             │
│  (bitcoind / ordexcoind / ordexgoldd)                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Service Ideas

### 1. Web Wallet Service

A hosted wallet service where users don't run their own node.

**Architecture:**
```
User Browser
    │
    ▼
Web Wallet Backend (Flask/FastAPI)
    │
    ├──► Ordex RPC Library
    │     ├── Address Service (HD derivation)
    │     ├── Transaction Service (build/sign)
    │     └── Notification Service (webhooks)
    │
    └──► Database (user accounts, encrypted keys)
```

**Key Features:**
- User registration / login
- HD wallet generation (BIP39 mnemonic backup)
- Receive addresses (BIP84)
- Send transactions
- Transaction history
- Multi-signature support
- Two-factor authentication

**Example Structure:**
```python
class WebWalletService:
    def __init__(self, rpc_services):
        self.rpc = rpc_services
        self.db = Database()
    
    def create_account(self, email, password):
        # Generate HD wallet
        mnemonic = BIP39.generate()
        wallet_id = self.rpc.address.generate("account")
        return self.db.save_account(email, mnemonic, wallet_id)
    
    def send(self, user_id, to_address, amount):
        account = self.db.get_account(user_id)
        tx = self.rpc.transactions.build(...)
        signed = self.rpc.transactions.sign(tx, account.wallet_id)
        result = self.rpc.transactions.broadcast(signed)
        self.rpc.tracker.track(result.txid, account.wallet_id, amount)
        return result.txid
```

---

### 2. Swap/Exchange Service

Atomic swap service between OXC and OXG (or other chains).

**Architecture:**
```
                    Swap Coordinator
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
    Party A                              Party B
(OXC Wallet)                          (OXG Wallet)
```

**Flow:**
1. Party A creates swap offer (OXC for OXG)
2. Party B accepts offer
3. Coordinator watches both chains
4. Atomic execution (hash-time-lock contracts)

**Key Components:**
```python
class SwapService:
    def __init__(self, oxc_services, oxg_services):
        self.oxc = oxc_services  # OrdexCoin services
        self.oxg = oxg_services  # OrdexGold services
        self.swap_db = SwapDatabase()
    
    def create_swap_offer(self, offer_coin, offer_amount, want_coin, want_amount):
        """Create a swap offer."""
        swap_id = generate_swap_id()
        
        # Lock funds in HTLC
        if offer_coin == "OXC":
            tx = self.oxc.transactions.build_htlc(...)
            self.oxc.broadcast(tx)
        else:
            tx = self.oxg.transactions.build_htlc(...)
            self.oxg.broadcast(tx)
        
        return SwapOffer(swap_id, ...)
    
    def accept_swap(self, swap_id, accepting_coin):
        """Accept and complete swap."""
        swap = self.swap_db.get(swap_id)
        
        # Watch both chains for HTLC reveal
        self.oxc.tracker.on_confirmation(swap.oxc_txid, callback)
        self.oxg.tracker.on_confirmation(swap.oxg_txid, callback)
        
        return swap.execute()
    
    def refund_expired(self, swap_id):
        """Refund if timelock expires without completion."""
        swap = self.swap_db.get(swap_id)
        swap.refund()
```

---

### 3. Blockchain Explorer

Block explorer API and frontend.

**Architecture:**
```
                    Explorer Backend
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
Block Service        Mempool Service    Tx Tracker
(headers, blocks)   (unconfirmed)       (search, history)

                    │
                    ▼
              Cached Database
              (PostgreSQL/Redis)
```

**Key Features:**
- Block listing and detail views
- Transaction search and details
- Address lookup and history
- Rich list / top holders
- Network stats dashboard
- Mempool visualization

**Example Structure:**
```python
class ExplorerService:
    def __init__(self, rpc_services, db):
        self.rpc = rpc_services
        self.db = db
        self._setup_subscriptions()
    
    def _setup_subscriptions(self):
        # Subscribe to new blocks
        self.rpc.blocks.on_new_block(self._on_new_block)
        
        # Subscribe to mempool changes
        self.rpc.mempool.on_new_transaction(self._on_new_tx)
    
    def get_block(self, height_or_hash):
        # Check cache first
        cached = self.db.get_block(height_or_hash)
        if cached:
            return cached
        
        # Fetch from node
        block = self.rpc.blocks.get_block(height_or_hash)
        
        # Cache and return
        self.db.save_block(block)
        return block
    
    def get_address_history(self, address):
        """Get all transactions for an address."""
        # Scan blockchain for address
        # OR use address index from full node
        
        unspents = self.rpc.client.listunspent(addresses=[address])
        history = []
        
        for utxo in unspents:
            history.append(Transaction(utxo))
        
        return AddressHistory(address, history)
    
    def search(self, query):
        """Search for block, tx, or address."""
        if len(query) == 64:  # txid or block hash
            tx = self.rpc.transactions.get(query)
            if tx:
                return SearchResult(type="transaction", data=tx)
        
        if query.isdigit():
            block = self.rpc.blocks.get_block(int(query))
            if block:
                return SearchResult(type="block", data=block)
        
        if self.rpc.address.validate(query):
            return SearchResult(type="address", data=self.get_address(query))
        
        return None
    
    def get_network_stats(self):
        """Aggregate network statistics."""
        stats = self.rpc.mempool.get_stats()
        tip = self.rpc.blocks.get_tip()
        
        return {
            "height": tip.get("height"),
            "difficulty": self.rpc.client.getblockchaininfo()["difficulty"],
            "mempool_size": stats.transaction_count,
            "mempool_fees": stats.fee_percentiles,
            "hash_rate": self._estimate_hash_rate(),
        }
```

---

### 4. Liquidity Pool Service

Automated market maker (AMM) for OXC/OXG swaps.

**Architecture:**
```
                  Liquidity Pool
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    Pool A          Pool B          Pool C
    (OXC/OXG)      (OXC/OXG)       (Custom)

        │              │              │
        ▼              ▼              ▼
    Ordex RPC ←────────────────────────┘
    (Transaction Service)
```

**Key Features:**
- Deposit liquidity (dual-chain)
- Automatic rebalancing
- Fee accumulation
- Liquidity provider tokens
- Impermanent loss tracking

**Example Structure:**
```python
class LiquidityPool:
    def __init__(self, oxc_services, oxg_services):
        self.oxc = oxc_services
        self.oxg = oxg_services
        self.reserves = {"OXC": 0, "OXG": 0}
        self.lp_tokens = {}
    
    def add_liquidity(self, depositor, oxc_amount, oxg_amount):
        """Add liquidity to the pool."""
        # Verify deposits
        # Calculate LP tokens to mint
        # Track reserves
        
        lp_tokens = self._calculate_lp_tokens(oxc_amount, oxg_amount)
        self.lp_tokens[depositor] = self.lp_tokens.get(depositor, 0) + lp_tokens
        
        return lp_tokens
    
    def swap(self, from_coin, from_amount, min_receive):
        """Execute a swap."""
        # Get quote
        quote = self._get_swap_quote(from_coin, from_amount)
        
        if quote < min_receive:
            raise SlippageError()
        
        # Execute on chain
        if from_coin == "OXC":
            tx = self.oxc.transactions.build_swap(quote, "OXG")
        else:
            tx = self.oxg.transactions.build_swap(quote, "OXC")
        
        result = self.oxc.transactions.broadcast(tx)
        
        # Update reserves
        self._update_reserves()
        
        return result
    
    def remove_liquidity(self, depositor, lp_tokens):
        """Withdraw liquidity."""
        share = lp_tokens / self.total_lp_tokens
        
        oxc_withdraw = self.reserves["OXC"] * share
        oxg_withdraw = self.reserves["OXG"] * share
        
        # Execute withdrawals on both chains
        self.oxc.transactions.send(depositor, oxc_withdraw)
        self.oxg.transactions.send(depositor, oxg_withdraw)
        
        self.lp_tokens[depositor] -= lp_tokens
```

---

### 5. Payment Processor

API for merchants to accept OXC/OXG payments.

**Architecture:**
```
                Payment Processor
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
Invoice Generator   Webhook Service    Settlement Engine
```

**Key Features:**
- Create invoices
- Payment verification
- Automatic settlement
- Multi-currency support
- Refund handling

**Example Structure:**
```python
class PaymentProcessor:
    def __init__(self, rpc_services):
        self.rpc = rpc_services
        self.invoices = {}
        self.webhook_url = None
    
    def create_invoice(self, amount, currency, order_id):
        """Create a payment invoice."""
        # Generate unique address
        address = self.rpc.address.generate("invoices")[0]
        
        invoice = Invoice(
            id=generate_id(),
            address=address,
            amount=self._convert_to_sats(amount, currency),
            order_id=order_id,
            created_at=now(),
            expires_at=now() + timedelta(hours=1),
        )
        
        self.invoices[invoice.id] = invoice
        
        # Track payments
        self._start_tracking(invoice)
        
        return invoice
    
    def _start_tracking(self, invoice):
        """Watch for payment to invoice address."""
        def on_payment(txid, info):
            tx = self.rpc.transactions.get(txid)
            
            if tx.confirmations >= 1:
                self._settle_invoice(invoice, tx)
        
        self.rpc.tracker.monitor(invoice.address, on_payment)
    
    def _settle_invoice(self, invoice, payment):
        """Settle invoice and notify merchant."""
        invoice.status = "paid"
        invoice.payment = payment
        
        # Send webhook
        if self.webhook_url:
            self._send_webhook(invoice)
        
        # Auto-settle to merchant wallet
        if invoice.auto_settle:
            self._settle_to_wallet(invoice)
    
    def _send_webhook(self, invoice):
        """Send payment notification."""
        payload = {
            "event": "payment.received",
            "invoice_id": invoice.id,
            "order_id": invoice.order_id,
            "amount": invoice.amount,
            "txid": invoice.payment.txid,
            "confirmations": invoice.payment.confirmations,
        }
        
        self.rpc.notifications.emit("payment", payload)
```

---

### 6. Node Monitoring Service

Infrastructure monitoring for Ordex nodes.

**Architecture:**
```
                Monitoring Dashboard
                       │
    ┌──────────────────┼──────────────────┐
    ▼                  ▼                  ▼
 NodeMonitor      HealthMonitor      AlertService
```

**Key Features:**
- Multi-node monitoring
- Uptime tracking
- Latency metrics
- Fee rate monitoring
- Alerting (email, SMS, Slack)
- Historical charts

**Example Structure:**
```python
class NodeMonitor:
    def __init__(self, rpc_client):
        self.rpc = rpc_client
        self.metrics_db = MetricsDB()
    
    def check_node_health(self):
        """Check all node health metrics."""
        try:
            start = time.time()
            info = self.rpc.getblockchaininfo()
            latency = time.time() - start
            
            return {
                "online": True,
                "height": info["blocks"],
                "latency_ms": latency * 1000,
                "mempool_size": len(self.rpc.getrawmempool()),
                "peers": self.rpc.getpeerinfo()["connected"],
            }
        except Exception as e:
            return {"online": False, "error": str(e)}
    
    def get_fee_estimate(self, target_blocks=6):
        """Get current fee estimates."""
        estimates = {}
        
        for mode in ["economical", "half_hour", "hour"]:
            fee = self.rpc.estimatesmartfee(target_blocks)
            estimates[mode] = fee["feerate"]
        
        return estimates
    
    def alert_on_threshold(self, metric, threshold, callback):
        """Set up alerting."""
        def check():
            value = self.metrics_db.get_current(metric)
            if value > threshold:
                callback(metric, value, threshold)
        
        # Run check periodically
        schedule.every(1).minutes.do(check)
```

---

## Common Patterns

### Multi-Network Support

Most services need to support both OXC and OXG:

```python
class DualNetworkService:
    def __init__(self):
        self.services = {
            "OXC": create_services(nodes=[...]),
            "OXG": create_services(nodes=[...]),
        }
    
    def get_service(self, coin):
        return self.services.get(coin.upper())
```

### Error Handling

```python
from ordex.rpc.client import RpcError

def handle_rpc_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RpcError as e:
            if e.code == -4:  # Transaction rejected
                return {"error": "tx_rejected", "message": str(e)}
            elif e.code == -6:  # Insufficient funds
                return {"error": "insufficient_funds"}
            raise
    return wrapper
```

### Rate Limiting

```python
from ratelimit import limits

class RateLimitedService:
    @limits(calls=10, period=1.0)  # 10 calls per second
    def call_rpc(self, method, *args):
        return self.rpc.call(method, *args)
```

---

## Next Steps

To build any of these services:

1. **Install the library:**
   ```bash
   pip install ordex
   ```

2. **Set up node RPC:**
   - Run `ordexcoind` or `ordexgoldd`
   - Configure RPC credentials

3. **Initialize services:**
   ```python
   from ordex.rpc import create_services
   services = create_services([{"url": "http://localhost:8332"}])
   ```

4. **Build your service layer** on top of the RPC services

5. **Add persistence** (database) for user data

6. **Add web interface** (Flask/FastAPI) for APIs

7. **Set up monitoring** and alerting

---

## Contributing

Ideas for additional services? Open an issue or PR!