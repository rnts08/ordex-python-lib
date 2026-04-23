# Ordex Python Library - Analysis & Plan

## Overview
This is a clean-room Python implementation of the **OrdexCoin (OXC)** and **OrdexGold (OXG)** blockchain protocols. The library provides:
- Multi-chain support (OXC/SHA-256d, OXG/Scrypt+MWEB)
- Block and transaction primitives with serialization
- PoW validation and difficulty retargeting
- Address generation and decoding (P2PKH, P2SH, Bech32)
- HD wallet support (BIP32/39)
- P2P networking (async TCP)
- JSON-RPC client

**Test Status**: 159 tests passing.

---

## Issues, Bugs, and Missing Features

### Completed (Fixed/Implemented)

1. ✅ **`Uint256.get_compact()` broken for zero** - Fixed with explicit zero handling
2. ✅ **MWEB transaction deserialization** - Now properly reads MWEB data and locktime
3. ✅ **MWEB block deserialization** - Added allow_mweb parameter, reads remaining bytes
4. ✅ **No address decoding** - Added p2pkh_to_pubkey_hash, bech32_to_pubkey_hash, decode_address
5. ✅ **Uint256 missing `__sub__` operation** - Added subtraction with wraparound
6. ✅ **Missing type annotations** - Added to generate_keypair, decode_address
7. ✅ **P2SH address in keypair** - generate_keypair() now includes p2sh output
8. ✅ **BIP32 HD wallet support** - ExtendedKey, HDWallet classes with full derivation
9. ✅ **BIP39 mnemonic support** - mnemonic_to_seed() with PBKDF2
10. ✅ **Transaction signing** - Can sign transactions with ECDSA
11. ✅ **P2P message handling** - MsgGetHeaders, MsgHeaders, MsgMerkleBlock, CAddress, MsgAddr, MsgMempool
12. ✅ **Block sync logic** - BlockSynchronizer, ChainState, PeerManager
13. ✅ **Mempool handling** - MsgMempool, get_peer_inventory()

### Missing Features

14. **No script execution/interpreter** - Cannot validate scripts (P2PKH, P2WSH, etc.)
15. **No block validation** - CBlock has no check() method to validate PoW
16. **No merkle block / SPV proofs** - MsgMerkleBlock implemented but no full SPV validation

### Minor Issues / Improvements

17. **Incomplete Regtest chain params** - Missing genesis_block_hash for testnet/regtest
18. **No fee estimation logic** - RPC has estimatesmartfee but no local implementation
19. **No logging configuration** - Uses logging but no setup/docs
20. **No CI/CD pipeline** - No GitHub Actions
21. **No documentation build** - No Sphinx configuration
22. **Taproot (BIP341/342) not supported** - P2TR addresses not implemented

---

## Recommended Plan

### Phase 1: Bug Fixes ✅ DONE
- [x] Fix Uint256.get_compact() for zero value
- [x] Add proper MWEB transaction deserialization
- [x] Add MWEB block deserialization

### Phase 2: Address & Key Improvements ✅ DONE
- [x] Add address decoding (P2PKH, P2SH, Bech32 → pubkey/script hash)
- [x] Add P2SH to generate_keypair()
- [x] Implement BIP32 HD wallet
- [x] Implement BIP39 mnemonic to seed

### Phase 3: Transaction & Script ✅ DONE
- [x] Implement transaction signing (ECDSA)
- [ ] Implement basic script interpreter
- [ ] Add Taproot (P2TR) support

### Phase 4: P2P & Networking ✅ DONE
- [x] Add MsgHeaders deserialization
- [x] Add block sync/headers download logic
- [x] Add MsgMerkleBlock for SPV
- [x] Add CAddress/MsgAddr for network addresses
- [x] Add MsgMempool for mempool requests

### Phase 5: Validation & Testing
- [ ] Add block validation (check_proof_of_work, merkle root check)
- [ ] Add test vectors from Ordex daemons
- [ ] Add CI/CD

### Phase 6: Polish
- [ ] Add Sphinx documentation
- [ ] Add logging configuration
- [ ] Complete Regtest params
- [ ] Type annotations cleanup

---

## Priority Order

| Priority | Item | Effort |
|----------|------|--------|
| High | Block validation | Medium |
| High | Script interpreter | High |
| Medium | Taproot (P2TR) support | High |
| Low | Documentation/CI | Medium |

---

*Generated: April 2026*
*Last Updated: April 2026*