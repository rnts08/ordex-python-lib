"""
Block synchronization logic for P2P networking.

Provides header download, block locator construction, and chain
state management for initial block download (IBD).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Set

from io import BytesIO

from ordex.chain.chainparams import ChainParams
from ordex.core.hash import sha256d
from ordex.net.connection import NodeConnection
from ordex.net.messages import MsgGetHeaders, MsgHeaders, MsgGetData, MsgInv
from ordex.net.protocol import CInv, InvType, NetMsgType
from ordex.primitives.block import CBlockHeader

logger = logging.getLogger(__name__)


class ChainState:
    """Tracks the local chain state during sync."""

    def __init__(self, params: ChainParams) -> None:
        self.params = params
        self.headers: Dict[bytes, CBlockHeader] = {}
        self.known_blocks: Set[bytes] = set()
        self.tip: Optional[bytes] = None
        self.height: int = 0

    def add_header(self, header: CBlockHeader) -> bool:
        """Add a header to the chain state.

        Returns True if this is a new header.
        """
        header_hash = sha256d(header.to_bytes())
        if header_hash in self.headers:
            return False

        self.headers[header_hash] = header
        self.known_blocks.add(header_hash)

        if self.tip is None or self._is_newer(header, self.headers.get(self.tip)):
            self.tip = header_hash
            self.height += 1

        return True

    def _is_newer(self, header: CBlockHeader, other: Optional[CBlockHeader]) -> bool:
        if other is None:
            return True
        return header.time > other.time

    def get_locator(self) -> List[bytes]:
        """Build a block locator for getheaders message."""
        if self.tip is None:
            return [b"\x00" * 32]

        locator = []
        hash = self.tip

        for i in range(10):
            if hash in self.headers:
                locator.append(hash)
                header = self.headers[hash]
                if header.hash_prev_block in self.headers:
                    hash = header.hash_prev_block
                else:
                    break
            else:
                break

        locator.append(b"\x00" * 32)
        return locator

    def find_gap(self, headers: List[CBlockHeader]) -> Optional[int]:
        """Find the first gap in the header chain.

        Returns the index where the gap starts, or None if contiguous.
        """
        if not headers:
            return None

        for i, header in enumerate(headers):
            header_hash = sha256d(header.to_bytes())
            prev_hash = header.hash_prev_block

            if self.tip is None and i == 0:
                if prev_hash != b"\x00" * 32:
                    continue
            elif prev_hash not in self.known_blocks and prev_hash != self.tip:
                return i

        return None


class BlockSynchronizer:
    """Handles header and block synchronization with peers.

    Usage::

        sync = BlockSynchronizer(conn, chain_params)
        await sync.download_headers(peer_height=800000)
        await sync.download_blocks()
    """

    MAX_HEADERS_PER_MSG = 2000
    MAX_BLOCKS_PER_MSG = 16

    def __init__(self, conn: NodeConnection, params: Optional[ChainParams] = None) -> None:
        self.conn = conn
        self.params = params or conn.params
        self.state = ChainState(self.params)

    async def download_headers(
        self,
        peer_height: int = 0,
        max_headers: int = 2000,
    ) -> List[CBlockHeader]:
        """Download block headers from peer.

        Args:
            peer_height: Known height of peer's chain tip
            max_headers: Maximum headers to request

        Returns:
            List of downloaded headers
        """
        downloaded: List[CBlockHeader] = []
        locators = self.state.get_locator()
        hash_stop = b"\x00" * 32

        while len(downloaded) < max_headers:
            msg = MsgGetHeaders(
                version=self.params.protocol_version,
                block_locator_hashes=locators,
                hash_stop=hash_stop,
            )

            await self.conn.send_message(NetMsgType.GETHEADERS, msg.to_bytes())

            cmd, payload = await self.conn.recv_message()
            if cmd != NetMsgType.HEADERS:
                logger.warning("Expected headers, got %s", cmd)
                break

            headers_msg = MsgHeaders.deserialize(BytesIO(payload))
            if not headers_msg.headers:
                logger.info("No more headers available")
                break

            for header in headers_msg.headers:
                self.state.add_header(header)
                downloaded.append(header)

            last_hash = sha256d(headers_msg.headers[-1].to_bytes())
            locators = [last_hash]

            if len(headers_msg.headers) < self.MAX_HEADERS_PER_MSG:
                break

        logger.info("Downloaded %d headers", len(downloaded))
        return downloaded

    async def request_block(self, block_hash: bytes) -> Optional[bytes]:
        """Request a specific block from the peer.

        Returns the serialized block or None if not received.
        """
        inv = CInv(InvType.MSG_BLOCK, block_hash)
        msg = MsgGetData(inventory=[inv])

        await self.conn.send_message(NetMsgType.GETDATA, msg.to_bytes())

        try:
            cmd, payload = await self.conn.recv_message(timeout=60.0)
            if cmd == NetMsgType.BLOCK:
                return payload
            elif cmd == NetMsgType.NOTFOUND:
                logger.warning("Block not found: %s", block_hash.hex())
                return None
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for block: %s", block_hash.hex())

        return None

    async def download_blocks(
        self,
        start_hash: Optional[bytes] = None,
        max_blocks: int = 16,
    ) -> List[bytes]:
        """Download blocks starting from a given hash.

        Args:
            start_hash: Hash to start from (default: tip)
            max_blocks: Maximum blocks to download

        Returns:
            List of serialized blocks
        """
        downloaded: List[bytes] = []

        if start_hash is None:
            start_hash = self.state.tip

        if start_hash is None:
            logger.warning("No blocks to download (no tip)")
            return downloaded

        inv = CInv(InvType.MSG_BLOCK, start_hash)
        msg = MsgGetData(inventory=[inv])

        await self.conn.send_message(NetMsgType.GETDATA, msg.to_bytes())

        for _ in range(max_blocks):
            try:
                cmd, payload = await self.conn.recv_message(timeout=60.0)
                if cmd == NetMsgType.BLOCK:
                    downloaded.append(payload)
                elif cmd == NetMsgType.INV:
                    inv_msg = MsgInv.deserialize(BytesIO(payload))
                    for inv_item in inv_msg.inventory:
                        if inv_item.is_block():
                            await self.request_block(inv_item.hash)
                elif cmd == NetMsgType.NOTFOUND:
                    break
                else:
                    logger.debug("Unexpected message during block download: %s", cmd)
            except asyncio.TimeoutError:
                break

        logger.info("Downloaded %d blocks", len(downloaded))
        return downloaded

    async def get_peer_inventory(self) -> List[CInv]:
        """Request mempool inventory from peer."""
        await self.conn.send_message(NetMsgType.MEMP, b"")

        inv_items: List[CInv] = []
        try:
            while True:
                cmd, payload = await self.conn.recv_message(timeout=30.0)
                if cmd == NetMsgType.INV:
                    inv_msg = MsgInv.deserialize(BytesIO(payload))
                    inv_items.extend(inv_msg.inventory)
                elif cmd == NetMsgType.NOTFOUND:
                    break
                else:
                    break
        except asyncio.TimeoutError:
            pass

        return inv_items


class PeerManager:
    """Manages connections to multiple peers and tracks their chain state."""

    def __init__(self, params: ChainParams) -> None:
        self.params = params
        self.connections: Dict[str, NodeConnection] = {}
        self.peer_heights: Dict[str, int] = {}
        self.best_peer: Optional[str] = None

    async def add_peer(self, host: str, port: int) -> bool:
        """Connect to a new peer and perform handshake.

        Returns True if connection successful.
        """
        try:
            conn = NodeConnection(host, port, self.params)
            await conn.connect()
            await conn.handshake()

            self.connections[f"{host}:{port}"] = conn

            if conn.peer_version:
                self.peer_heights[f"{host}:{port}"] = conn.peer_version.start_height
                self._update_best_peer()

            logger.info("Connected to peer %s:%d", host, port)
            return True

        except Exception as e:
            logger.error("Failed to connect to %s:%d: %s", host, port, e)
            return False

    def _update_best_peer(self) -> None:
        if not self.peer_heights:
            return

        best = max(self.peer_heights.items(), key=lambda x: x[1])
        self.best_peer = best[0]

    async def disconnect_peer(self, host: str, port: int) -> None:
        """Disconnect from a peer."""
        key = f"{host}:{port}"
        if key in self.connections:
            await self.connections[key].close()
            del self.connections[key]
            if key in self.peer_heights:
                del self.peer_heights[key]
            if self.best_peer == key:
                self.best_peer = None
                self._update_best_peer()

    async def close_all(self) -> None:
        """Close all peer connections."""
        for conn in list(self.connections.values()):
            await conn.close()
        self.connections.clear()
        self.peer_heights.clear()
        self.best_peer = None