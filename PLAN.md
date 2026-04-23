# Ordex Python Library - Analysis & Plan

## Overview
This is a clean-room Python implementation of the OrdexCoin (OXC) and OrdexGold (OXG) blockchain protocols. The library provides:
- Multi-chain support (OXC/SHA-256d, OXG/Scrypt+MWEB)
- Block and transaction primitives with serialization
- PoW validation and difficulty retargeting
- Address generation and decoding (P2PKH, P2SH, Bech32)
- P2P networking (async TCP)
- JSON-RPC client

**Test Status**: 91 tests passing.

---

## Issues, Bugs, and Missing Features

### Completed (Fixed/Implemented)

1. ✅ **`Uint256.get_compact()` broken for zero** - Fixed with explicit zero handling
2. ✅ **MWEB transaction deserialization** - Now properly reads MWEB data and locktime
3. ✅ **MWEB block deserialization** - Added allow_mweb parameter, reads remaining bytes
4. ✅ **No address decoding** - Added p2pkh_to_pubkey_hash, bech32_to_pubkey_hash, decode_address
5. ✅ **Uint256 missing `__sub__` operation** - Added subtraction with wraparound
6. ✅ **Missing type annotations** - Added to generate_keypair, decode_address

### Missing Features

7. **No P2SH address in keypair** - generate_keypair() missing p2sh output
8. **No BIP32 HD wallet support** - No hierarchical deterministic key derivation
9. **No BIP39 mnemonic support** - No seed phrase functionality
10. **No transaction signing** - Can create transactions but cannot sign them
11. **No script execution/interpreter** - Cannot validate scripts (P2PKH, P2WSH, etc.)
12. **Incomplete P2P message handling**
    - `MsgGetHeaders` has no deserialize method
    - No `MsgHeaders` implementation
    - No block download/sync logic
13. **No merkle block / SPV proofs** - No MsgMerkleBlock implementation
14. **No block validation** - CBlock has no check() method to validate PoW
15. **No mempool handling** - No mempool data structures or RPC

### Minor Issues / Improvements

16. **Incomplete Regtest chain params** - Missing genesis_block_hash for testnet/regtest
17. **No fee estimation logic** - RPC has estimatesmartfee but no local implementation
18. **No logging configuration** - Uses logging but no setup/docs
19. **No CI/CD pipeline** - No GitHub Actions
20. **No documentation build** - No Sphinx configuration
21. **Taproot (BIP341/342) not supported** - P2TR addresses not implemented

---

## Recommended Plan

### Phase 1: Bug Fixes ✅ DONE
- [x] Fix Uint256.get_compact() for zero value
- [x] Add proper MWEB transaction deserialization
- [x] Add MWEB block deserialization

### Phase 2: Address & Key Improvements ✅ DONE
- [x] Add address decoding (P2PKH, P2SH, Bech32 → pubkey/script hash)
- [ ] Add P2SH to generate_keypair()
- [ ] Implement BIP32 HD wallet

### Phase 3: Transaction & Script
- [ ] Implement transaction signing (ECDSA)
- [ ] Implement basic script interpreter
- [ ] Add Taproot (P2TR) support

### Phase 4: P2P & Networking
- [ ] Add MsgHeaders deserialization
- [ ] Add block sync/headers download logic
- [ ] Add MsgMerkleBlock for SPV

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
| High | Add P2SH to generate_keypair | Low |
| Medium | Block validation | Medium |
| Medium | Transaction signing | High |
| Medium | Script interpreter | High |
| Low | BIP32/39 support | High |
| Low | P2P message handling | Medium |
| Low | Documentation/CI | Medium |

---

*Generated: April 2026*
*Last Updated: April 2026*