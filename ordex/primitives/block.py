"""
Block primitives for OrdexCoin and OrdexGold.

Implements CBlockHeader and CBlock with chain-aware PoW hash computation,
Merkle tree calculation, and genesis block creation.
"""

from __future__ import annotations

from io import BytesIO
from typing import BinaryIO, List, Optional

from ordex.core.hash import sha256d, scrypt_hash, merkle_hash
from ordex.core.script import CScript, CScriptNum, OP_CHECKSIG
from ordex.core.serialize import (
    read_int32, write_int32,
    read_uint32, write_uint32,
    read_hash256, write_hash256,
    read_compact_size, write_compact_size,
)
from ordex.primitives.transaction import CTransaction, COutPoint, CTxIn, CTxOut


class CBlockHeader:
    """Standard 80-byte block header.

    Fields:
        version: Block version (int32)
        hash_prev_block: Hash of the previous block (32 bytes, internal order)
        hash_merkle_root: Merkle root of transactions (32 bytes)
        time: Block timestamp (uint32, Unix epoch)
        bits: Compact difficulty target (uint32)
        nonce: Mining nonce (uint32)
    """

    HEADER_SIZE = 80

    __slots__ = ("version", "hash_prev_block", "hash_merkle_root", "time", "bits", "nonce")

    def __init__(
        self,
        version: int = 0,
        hash_prev_block: bytes = b"\x00" * 32,
        hash_merkle_root: bytes = b"\x00" * 32,
        time: int = 0,
        bits: int = 0,
        nonce: int = 0,
    ) -> None:
        self.version = version
        self.hash_prev_block = hash_prev_block
        self.hash_merkle_root = hash_merkle_root
        self.time = time
        self.bits = bits
        self.nonce = nonce

    def serialize(self, f: BinaryIO) -> None:
        write_int32(f, self.version)
        write_hash256(f, self.hash_prev_block)
        write_hash256(f, self.hash_merkle_root)
        write_uint32(f, self.time)
        write_uint32(f, self.bits)
        write_uint32(f, self.nonce)

    @classmethod
    def deserialize(cls, f: BinaryIO) -> "CBlockHeader":
        return cls(
            version=read_int32(f),
            hash_prev_block=read_hash256(f),
            hash_merkle_root=read_hash256(f),
            time=read_uint32(f),
            bits=read_uint32(f),
            nonce=read_uint32(f),
        )

    def to_bytes(self) -> bytes:
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes) -> "CBlockHeader":
        return cls.deserialize(BytesIO(data))

    def get_hash(self) -> bytes:
        """Block identification hash — always SHA-256d for both chains.

        This is the hash used for block IDs, prev_block references, etc.
        """
        return sha256d(self.to_bytes())

    def get_pow_hash(self, use_scrypt: bool = False) -> bytes:
        """Proof-of-work hash.

        Args:
            use_scrypt: If True, use Scrypt (OrdexGold). Otherwise SHA-256d (OrdexCoin).
        """
        header_bytes = self.to_bytes()
        if use_scrypt:
            return scrypt_hash(header_bytes)
        return sha256d(header_bytes)

    def get_hash_hex(self) -> str:
        """Block hash as display hex (reversed byte order)."""
        return self.get_hash()[::-1].hex()

    def is_null(self) -> bool:
        return self.bits == 0

    def __repr__(self) -> str:
        return f"CBlockHeader(hash={self.get_hash_hex()[:16]}..., height_bits={self.bits:#x})"


class CBlock(CBlockHeader):
    """A full block: header + transaction list.

    For OrdexGold, blocks may also contain an MWEB block body stored as
    opaque data (``mweb_block_data``).
    """

    __slots__ = ("vtx", "mweb_block_data", "_checked")

    def __init__(self, header: Optional[CBlockHeader] = None, **kwargs) -> None:
        if header:
            super().__init__(
                version=header.version,
                hash_prev_block=header.hash_prev_block,
                hash_merkle_root=header.hash_merkle_root,
                time=header.time,
                bits=header.bits,
                nonce=header.nonce,
            )
        else:
            super().__init__(**kwargs)

        self.vtx: List[CTransaction] = []
        self.mweb_block_data: bytes = b""
        self._checked = False

    def serialize(self, f: BinaryIO) -> None:
        # Header
        super().serialize(f)
        # Transactions
        write_compact_size(f, len(self.vtx))
        for tx in self.vtx:
            tx.serialize(f)
        # MWEB block data (if present)
        if self.mweb_block_data:
            f.write(self.mweb_block_data)

    @classmethod
    def deserialize(cls, f: BinaryIO, *, allow_mweb: bool = False) -> "CBlock":
        header = CBlockHeader.deserialize(f)
        block = cls(header=header)
        tx_count = read_compact_size(f)
        block.vtx = [CTransaction.deserialize(f) for _ in range(tx_count)]
        
        # MWEB block data - read remaining bytes if present and allowed
        if allow_mweb:
            remaining = f.read()
            if remaining:
                block.mweb_block_data = remaining
        
        return block

    def to_bytes(self, include_mweb: bool = True) -> bytes:
        """Serialize the block to bytes."""
        buf = BytesIO()
        self.serialize(buf)
        return buf.getvalue()

    @classmethod
    def from_bytes(cls, data: bytes, *, allow_mweb: bool = False) -> "CBlock":
        """Deserialize a block from bytes."""
        return cls.deserialize(BytesIO(data), allow_mweb=allow_mweb)

    def get_header(self) -> CBlockHeader:
        return CBlockHeader(
            version=self.version,
            hash_prev_block=self.hash_prev_block,
            hash_merkle_root=self.hash_merkle_root,
            time=self.time,
            bits=self.bits,
            nonce=self.nonce,
        )

    def check(self, params, check_pow: bool = True) -> bool:
        """Validate the block.
        
        Checks:
        - First transaction is coinbase
        - No duplicate transactions
        - Merkle root matches transactions
        - PoW (proof of work) - optional, enabled by default
        
        Args:
            params: ChainParams or ConsensusParams
            check_pow: Whether to validate proof of work (default: True)
            
        Returns:
            True if block is valid
            
        Raises:
            ValueError: If validation fails
        """
        from ordex.consensus.pow import check_proof_of_work
        from ordex.consensus.params import ConsensusParams
        
        # Get consensus params
        if isinstance(params, ConsensusParams):
            consensus = params
        else:
            consensus = params.consensus
        
        # Check first transaction is coinbase
        if not self.vtx or not self.vtx[0].is_coinbase():
            raise ValueError("First transaction must be coinbase")
        
        # Check for duplicate transactions
        tx_ids = [tx.txid() for tx in self.vtx]
        if len(tx_ids) != len(set(tx_ids)):
            raise ValueError("Duplicate transactions in block")
        
        # Check merkle root
        tx_hashes = [tx.txid() for tx in self.vtx]
        computed_merkle = compute_merkle_root(tx_hashes)
        if computed_merkle != self.hash_merkle_root:
            raise ValueError(
                f"Merkle root mismatch: computed={computed_merkle.hex()}, "
                f"header={self.hash_merkle_root.hex()}"
            )
        
        # Check PoW (optional - can be disabled for testing)
        if check_pow:
            pow_hash = self.get_pow_hash(use_scrypt=consensus.use_scrypt)
            if not check_proof_of_work(pow_hash, self.bits, consensus):
                raise ValueError("Proof of work check failed")
        
        return True


class InvalidBlock(Exception):
    """Exception raised when block validation fails."""
    pass


# ---------------------------------------------------------------------------
# Merkle tree computation
# ---------------------------------------------------------------------------

def compute_merkle_root(tx_hashes: List[bytes]) -> bytes:
    """Compute the Merkle root from a list of transaction hashes.

    Each hash should be in internal byte order (as returned by sha256d).
    If the list has odd length, the last element is duplicated.
    """
    if not tx_hashes:
        return b"\x00" * 32

    level = list(tx_hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])  # duplicate last
        next_level = []
        for i in range(0, len(level), 2):
            next_level.append(merkle_hash(level[i], level[i + 1]))
        level = next_level
    return level[0]


# ---------------------------------------------------------------------------
# Genesis block creation
# ---------------------------------------------------------------------------

def create_genesis_block(
    timestamp_str: str,
    genesis_output_script: bytes,
    ntime: int,
    nnonce: int,
    nbits: int,
    nversion: int,
    genesis_reward: int,
) -> CBlock:
    """Create a genesis block matching the C++ CreateGenesisBlock() function.

    Args:
        timestamp_str: The coinbase script timestamp string (e.g. "Memento Mori")
        genesis_output_script: The output scriptPubKey (serialized CScript)
        ntime: Block timestamp
        nnonce: Block nonce
        nbits: Compact difficulty target
        nversion: Block version
        genesis_reward: Coinbase reward in satoshis
    """
    # Build the coinbase transaction
    # scriptSig: push 486604799 (0x1d00ffff as LE int) << push CScriptNum(4) << push timestamp string
    script_sig = (
        bytes([4])  # push 4 bytes
        + (486604799).to_bytes(4, "little")
        + bytes([1])  # push 1 byte
        + CScriptNum.encode(4)
        + bytes([len(timestamp_str)])
        + timestamp_str.encode("ascii")
    )

    coinbase_in = CTxIn(
        prevout=COutPoint(b"\x00" * 32, 0xFFFFFFFF),
        script_sig=script_sig,
        sequence=0xFFFFFFFF,
    )

    coinbase_out = CTxOut(
        value=genesis_reward,
        script_pubkey=genesis_output_script,
    )

    coinbase_tx = CTransaction(
        version=1,
        vin=[coinbase_in],
        vout=[coinbase_out],
        locktime=0,
    )

    # Build the block
    block = CBlock(
        version=nversion,
        hash_prev_block=b"\x00" * 32,
        hash_merkle_root=b"\x00" * 32,  # will be set below
        time=ntime,
        bits=nbits,
        nonce=nnonce,
    )
    block.vtx = [coinbase_tx]
    block.hash_merkle_root = compute_merkle_root([coinbase_tx.txid()])

    return block
