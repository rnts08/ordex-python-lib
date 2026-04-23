# Ordex Python Library v1.0.0 Release Notes

## Overview

Ordex-python-lib is a clean-room Python implementation of the OrdexCoin (OXC) and OrdexGold (OXG) blockchain protocols. This release provides a complete toolkit for building services and tools that interact with the Ordex network.

## Version

**v1.0.0** - April 2026

## Test Status

**339 tests passing** - All tests green

---

## Major Features

### Core Primitives

- **Multi-chain support**: OXC (SHA-256d) and OXG (Scrypt+MWEB) in a single library
- **Block handling**: CBlock, CBlockHeader with full serialization
- **Transaction handling**: CTransaction, CTxIn, CTxOut, COutPoint
- **Script primitives**: CScript, CScriptNum, opcode constants
- **Address types**: P2PKH, P2SH, P2WPKH (Bech32), P2TR (Taproot)

### Wallet & Keys

- **HD Wallet (BIP32)**: Hierarchical deterministic key derivation
- **Mnemonic support (BIP39)**: Seed generation from mnemonic phrases
- **Key generation**: PrivateKey, PublicKey with secp256k1
- **Address generation**: Full chain-specific address generation

### Transaction Signing

- **P2PKH signing**: sign_p2pkh_input()
- **Multi-input transactions**: create_signed_transaction()
- **Sighash types**: SIGHASH_ALL, SIGHASH_NONE, SIGHASH_SINGLE, SIGHASH_ANYONECANPAY

### Script Interpreter

- **Validation**: Basic script validation for P2PKH, P2WPKH
- **Extended opcodes**: OP_DUP, OP_HASH160, OP_EQUAL, OP_EQUALVERIFY, OP_CHECKSIG, OP_CHECKMULTISIG, OP_RETURN
- **Flow control**: OP_IF, OP_NOTIF, OP_ELSE, OP_ENDIF, OP_VERIFY
- **Locktime**: OP_CHECKLOCKTIMEVERIFY, OP_CHECKSEQUENCEVERIFY

### Consensus

- **PoW validation**: check_proof_of_work() for SHA-256d and Scrypt
- **Difficulty retargeting**: get_next_target()
- **Block subsidy**: get_block_subsidy()
- **Fee estimation**: FeeEstimator with local + RPC fallback

### P2P Networking

- **Connections**: Async TCP via NodeConnection
- **Messages**: MsgVersion, MsgInv, MsgHeaders, MsgGetHeaders, MsgMerkleBlock, MsgAddr, MsgMempool
- **Block sync**: BlockSynchronizer for header downloading
- **Peer management**: PeerManager, ChainState

### RPC Client

- **Full JSON-RPC**: RpcClient for ordexcoind/ordexgoldd
- **Convenience methods**: getblockchaininfo, getblock, sendrawtransaction, etc.

### Chain Parameters

Pre-configured for:
- OXC mainnet (25174 P2P, 25175 RPC)
- OXC testnet
- OXC regtest
- OXG mainnet (25466 P2P, 25467 RPC)
- OXG testnet
- OXG regtest

---

## Quick Start

```bash
# Install
pip install -e .

# Generate address
from ordex.wallet.address import generate_keypair
kp = generate_keypair(oxc_mainnet())
print(kp['p2pkh'])  # X...

# HD Wallet
from ordex.wallet.hd import HDWallet
wallet = HDWallet.from_mnemonic(oxc_mainnet(), "your mnemonic")
addr = wallet.derive_address(wallet.derive_external_chain(wallet.derive_account(0)), 0)
print(addr['p2pkh'])

# Sign transaction
from ordex.wallet.signing import create_signed_transaction
tx = create_signed_transaction(
    inputs=[('prevout_hash', 0, amount)],
    outputs=[('address', amount)],
    privkey=private_key
)
```

---

## Documentation

- **Sphinx docs**: Run `sphinx-build -b html docs docs/_build`
- **README**: Full usage examples in README.md
- **Tests**: 339 tests covering all major functionality

---

## Architecture

```
ordex/
├── core/           # Serialization, hashing, keys, base58, script
├── primitives/     # CTransaction, CBlock, CBlockHeader  
├── consensus/      # PoW, difficulty, subsidy, fees
├── chain/          # Chain parameters (OXC/OXG)
├── net/            # P2P protocol, messages, connections, sync
├── rpc/            # JSON-RPC client
└── wallet/         # Address generation, HD wallet, signing
```

---

## Dependencies

- ecdsa (>=0.18)
- requests (>=2.28)

---

## License

Copyright (c) 2026 ORDEX PROTOCOL/Timh Bergstrom. All rights reserved.

See LICENSE.md for details.