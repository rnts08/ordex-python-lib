Ordex Python Library
====================

A clean-room Python implementation of the OrdexCoin (OXC) and OrdexGold (OXG) blockchain protocols.

Features
--------

- Multi-chain support (OXC/SHA-256d, OXG/Scrypt+MWEB)
- Block and transaction primitives with serialization
- PoW validation and difficulty retargeting
- Address generation and decoding (P2PKH, P2SH, Bech32, P2TR)
- HD wallet support (BIP32/39)
- Script interpreter for basic validation
- Block validation with PoW and merkle root checks
- Fee estimation (local + RPC fallback)
- P2P networking (async TCP)
- JSON-RPC client

Quick Start
-----------

Generate a wallet:

.. code-block:: python

    from ordex.wallet.hd import HDWallet, ExtendedKey
    from ordex.wallet.bip39 import mnemonic_to_seed
    from ordex.chain.chainparams import get_chain_params

    seed = mnemonic_to_seed(
        "abandon " * 11 + "about",
        passphrase=""
    )
    params = get_chain_params("OXC")
    ek = ExtendedKey.from_seed(seed, params)
    wallet = HDWallet(ek, params)

    address = wallet.address(0)

Create a transaction:

.. code-block:: python

    from ordex.primitives.transaction import CTransaction, CTxIn, CTxOut

    tx = CTransaction()

    txin = CTxIn(prevout=...)
    tx.vin.append(txin)

    txout = CTxOut(nValue=100000, script_pubkey=...)
    tx.vout.append(txout)

API Reference
------------

.. toctree::
   :maxdepth: 2

   api/modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`