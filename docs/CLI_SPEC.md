# Ordex RPC CLI Daemon Specification

## Overview

CLI daemon that provides full RPC server functionality for both OrdexCoin and OrdexGold networks. Can run as:

1. **Combined server** - Single process handling one or both networks
2. **Network-specific** - Separate instance per network
3. **Light mode** - Uses existing node RPC (library acts as client)
4. **Full mode** - Library provides all wallet functionality on top of existing node

## Architecture

```
ordex-rpc (CLI)
├── ordex/library (RPC Services)
│   ├── Network Monitor (multi-node management)
│   ├── Health Monitor (system health)
│   ├── Mempool Service (fees, mempool)
│   ├── Block Service (block data)
│   ├── Address Service (HD derivation)
│   ├── Transaction Service (build/sign/broadcast)
│   ├── Tx Tracker (confirmation tracking)
│   └── Notification Service (events/webhooks)
│
└── ordex/wallet (Wallet functionality)
    ├── WalletManager (multi-wallet)
    ├── UTXO selection
    └── Transaction signing
```

## Usage Modes

### Mode 1: Library Mode (Uses Existing Node)

The library connects to existing bitcoind/ordexcoind and provides enhanced wallet features.

```bash
# Connect to local node
ordex-rpc --network ordexcoin

# Connect to remote node
ordex-rpc --network ordexcoin --rpcconnect 192.168.1.100

# Connect to both
ordex-rpc --network all
```

### Mode 2: Light Mode (Library Only)

Library provides wallet functions but connects to node for blockchain data.

```bash
ordex-rpc light --network ordexcoin
```

### Mode 3: Full Node (Future)

Library includes embedded node (not implemented in v1.1.0).

## Command Structure

```
ordex-rpc <command> [options]

Commands:
  start           Start RPC server
  stop            Stop RPC server
  wallet          Wallet operations
  getblockchaininfo  Get blockchain info
  getblock         Get block by height/hash
  getmempoolinfo   Get mempool info
  estimatesmartfee Get fee estimates
  sendtoaddress   Send coins
  getnewaddress   Get new address
  listwallets     List wallets
  help            Show help

Options:
  --network NETWORK  ordexcoin|ordexgold|all (default: ordexcoin)
  --port PORT       RPC port (default: network default)
  --rpcconnect HOST RPC host (default: 127.0.0.1)
  --rpcuser USER    RPC username
  --rpcpassword PASS RPC password
  --datadir DIR    Data directory
  --verbose        Verbose output
  --daemon        Run as daemon
```

## Network Ports

| Network   | RPC Port | P2P Port |
|-----------|---------|----------|
| OrdexCoin | 8332    | 8333     |
| OrdexGold | 19332   | 19333    |

## Commands

### Server Commands

```bash
# Start server as daemon
ordex-rpc start --network ordexcoin --daemon

# Start on custom port
ordex-rpc start --network ordexcoin --port 9032

# Start both networks
ordex-rpc start --network all

# Stop server
ordex-rpc stop --network ordexcoin

# Status
ordex-rpc status
```

### Wallet Commands

```bash
# Create wallet
ordex-rpc wallet create my_wallet

# List wallets
ordex-rpc wallet list

# Get balance
ordex-rpc wallet balance my_wallet

# Get new address
ordex-rpc wallet getnewaddress my_wallet

# Send transaction
ordex-rpc wallet send my_wallet <address> 1.0

# List transactions
ordex-rpc wallet txs my_wallet
```

### Blockchain Commands

```bash
# Get blockchain info
ordex-rpc getblockchaininfo

# Get block count
ordex-rpc getblockcount

# Get block by height
ordex-rpc getblock 100000

# Get block by hash
ordex-rpc getblock 000000...1

# Get mempool info
ordex-rpc getmempoolinfo

# Get raw mempool
ordex-rpc getrawmempool
```

### Network Commands

```bash
# Get network info
ordex-rpc getnetworkinfo

# Get peer info
ordex-rpc getpeerinfo

# Add node
ordex-rpc addnode 10.0.0.1:8333 add

# Remove node
ordex-rpc addnode 10.0.0.1:8333 remove
```

### Transaction Commands

```bash
# Create transaction
ordex-rpc createtransaction <from> <to> <amount>

# Sign transaction
ordex-rpc signtransaction <hex>

# Send transaction
ordex-rpc sendtransaction <hex>

# Decode transaction
ordex-rpc decoderawtransaction <hex>
```

### Fee Commands

```bash
# Estimate fee
ordex-rpc estimatesmartfee 6

# Get all estimates
ordex-rpc feeestimates
```

## Implementation

### Entry Point

`bin/ordex-rpc` - Main CLI entry point

```python
#!/usr/bin/env python3
"""Ordex RPC CLI daemon."""

import sys
import argparse
from ordex.rpc.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

### Module Structure

```
ordex/rpc/
├── __init__.py           # Exports
├── services.py          # OrdexServices container
├── network.py          # Network Monitor
├── health.py           # Health Monitor
├── mempool.py          # Mempool Service
├── block.py           # Block Service
├── address.py         # Address Service
├── transaction.py    # Transaction Service
├── tracker.py       # Tx Tracker
├── notifications.py # Notification Service
├── client.py      # Base RPC client
├── cli.py        # CLI commands
├── daemon.py     # Daemon process
└── config.py    # Configuration
```

## Configuration Files

### ~/.ordex/ordex.conf

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

[default]
network=ordexcoin
datadir=~/.ordex
logfile=~/.ordex/ordex.log
```

### Environment Variables

```bash
OXR_RPC_NETWORK=ordexcoin
OXR_RPC_USER=rpcuser
OXR_RPC_PASSWORD=rpcpass
OXR_DATA_DIR=~/.ordex
OXR_LOG_LEVEL=INFO
```