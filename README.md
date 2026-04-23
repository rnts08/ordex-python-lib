# Ordex Protocol — Python Implementation

[![Tests](https://github.com/rnts08/ordex-python-lib/actions/workflows/tests.yml/badge.svg)](https://github.com/rnts08/ordex-python-lib/actions/workflows/tests.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/ordex)](https://pypi.org/project/ordex/)
[![License](https://img.shields.io/github/license/rnts08/ordex-python-lib)](LICENSE.md)

Clean-room Python implementation of the **OrdexCoin (OXC)** and **OrdexGold (OXG)** blockchain protocols.

## Features

- **Multi-chain support**: Single library handles both OXC (SHA-256d) and OXG (Scrypt + MWEB)
- **Full primitive types**: Block headers, transactions, scripts, and serialization
- **Consensus rules**: PoW validation, difficulty retargeting, block subsidy
- **Address generation**: P2PKH, P2SH, Bech32 (P2WPKH) with correct chain prefixes
- **HD Wallet**: BIP32 hierarchical deterministic keys, BIP39 mnemonic support
- **Transaction signing**: ECDSA transaction signing for P2PKH inputs
- **Script interpreter**: Basic script validation for P2PKH, P2WPKH
- **Block validation**: PoW and merkle root verification
- **P2P networking**: Async TCP connection, header/block sync, multi-peer management
- **RPC client**: JSON-RPC interface to ordexcoind / ordexgoldd

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .

# Run tests
pytest tests/ -v
```

## Usage Examples

### Generate an Address

```python
from ordex.chain.chainparams import oxc_mainnet, oxg_mainnet
from ordex.wallet.address import generate_keypair

# OrdexCoin address
kp = generate_keypair(oxc_mainnet())
print(f"OXC P2PKH: {kp['p2pkh']}")    # X...
print(f"OXC P2SH:  {kp['p2sh']}")     # 7...
print(f"OXC Bech32: {kp['p2wpkh']}")  # oxc1...
print(f"OXC WIF:    {kp['wif']}")

# OrdexGold address
kp = generate_keypair(oxg_mainnet())
print(f"OXG P2PKH: {kp['p2pkh']}")    # G...
print(f"OXG Bech32: {kp['p2wpkh']}")  # oxg1...
```

### HD Wallet (BIP32/39)

```python
from ordex.chain.chainparams import oxc_mainnet
from ordex.wallet.hd import HDWallet
from ordex.wallet.bip39 import mnemonic_to_seed

# From mnemonic
mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
wallet = HDWallet.from_mnemonic(oxc_mainnet(), mnemonic)

# Derive addresses
account = wallet.derive_account(0)
external = wallet.derive_external_chain(account)
addr = wallet.derive_address(external, 0)

print(f"Address: {addr['p2pkh']}")
print(f"Path: {addr['path']}")  # m/44'/0'/0'/0/0
```

### RPC Client

```python
from ordex.rpc.client import RpcClient

rpc = RpcClient("http://127.0.0.1:25175", "rpcuser", "rpcpass")
info = rpc.getblockchaininfo()
print(f"Chain: {info['chain']}, Height: {info['blocks']}")
```

### P2P Connection

```python
import asyncio
from ordex.chain.chainparams import oxc_mainnet
from ordex.net.connection import NodeConnection

async def main():
    conn = NodeConnection("127.0.0.1", 25174, oxc_mainnet())
    await conn.connect()
    await conn.handshake()
    print(f"Peer: {conn.peer_version.user_agent}")
    await conn.close()

asyncio.run(main())
```

### Block Synchronization

```python
import asyncio
from ordex.chain.chainparams import oxc_mainnet
from ordex.net.connection import NodeConnection
from ordex.net.sync import BlockSynchronizer

async def main():
    conn = NodeConnection("127.0.0.1", 25174, oxc_mainnet())
    await conn.connect()
    await conn.handshake()
    
    sync = BlockSynchronizer(conn, oxc_mainnet())
    headers = await sync.download_headers(peer_height=800000)
    print(f"Downloaded {len(headers)} headers")
    
    await conn.close()

asyncio.run(main())
```

## Architecture

```
ordex/
├── core/           # Serialization, hashing, keys, base58, script
├── primitives/     # CTransaction, CBlock, CBlockHeader
├── consensus/      # PoW, difficulty, subsidy, amount
├── chain/          # Chain parameters (OXC/OXG × mainnet/testnet/regtest)
├── net/            # P2P protocol, messages, async connections, sync
├── rpc/            # JSON-RPC client
└── wallet/         # Address generation, HD wallet, BIP39
```

## Protocol Differences

| Feature | OrdexCoin (OXC) | OrdexGold (OXG) |
|---------|----------------|-----------------|
| PoW Algorithm | SHA-256d | Scrypt |
| MWEB | No | Yes |
| Max Supply | 8,450,000 | 1,001,000 |
| Halving Interval | 210,000 blocks | 239,000 blocks |
| Address Prefix | X (76) | G (39) |
| Bech32 HRP | oxc | oxg |
| Default Port | 25174 | 25466 |

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_hd.py -v

# Run with coverage
pytest tests/ --cov=ordex
```

**Test Status**: 205 tests passing

## Support

This is an open-source project maintained by Timh Bergstrom and the OrdexNetwork community. To support the development efforts you can donate to the following addresses:

    * BTC: bc1qkmzc6d49fl0edyeynezwlrfqv486nmk6p5pmta
    * ETH/ERC-20: 0xC13D012CdAae7978CAa0Ef5B1E30ac6e65e6b17F
    * LTC: ltc1q0ahxru7nwgey64agffr7x89swekj7sz8stqc6x
    * SOL: HB2o6q6vsW5796U5y7NxNqA7vYZW1vuQjpAHDo7FAMG8
    * XRP: rUW7Q64vR4PwDM3F27etd6ipxK8MtuxsFs

To support tests and implementation with the ordexnetwork, you can help by donating tokens that will be used for testing and refining the system. 

    * OXC: oxc1q3psft0hvlslddyp8ktr3s737req7q8hrl0rkly
    * OXG: oxg1q34apjkn2yc6rsvuua98432ctqdrjh9hdkhpx0t

You can also [Buy me a coffee](https://buymeacoffee.com/timhbergsta). For issues and contributions, visit the [GitHub repository](https://github.com/rnts08/ordex-python-lib).

## License

See [LICENSE.md](LICENSE.md) for details.

Copyright (c) 2026 ORDEX PROTOCOL/Timh Bergstrom. All rights reserved.