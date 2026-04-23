# Ordex Python Library - Release Notes

## v1.0.0

### Features
- Multi-chain support (OXC/SHA-256d, OXG/Scrypt+MWEB)
- BIP32/39 HD wallet support
- Script interpreter with extended opcodes
- Block and transaction primitives
- P2P networking (async TCP)
- JSON-RPC client
- Fee estimation (local + RPC fallback)
- Taproot (P2TR) support
- Sphinx documentation

### Testing
- **339 tests passing**
- Coverage for Uint256, RPC, Amount, NodeConnection
- Edge case tests for base58 encoding

### Code Quality
- Bare except clauses are intentional for error recovery
- Proper error messages in validation
- Logging throughout networking

### Build
- Clean repository (no cache/pyc files)
- Ready for release

*Generated: April 2026*