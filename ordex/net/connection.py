"""
Async P2P node connection handler.

Manages TCP connections to ordexcoind / ordexgoldd nodes,
performs the version handshake, and provides send/receive primitives.
"""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Callable, Dict, Optional

from ordex.chain.chainparams import ChainParams
from ordex.core.hash import sha256d
from ordex.net.protocol import CMessageHeader, NetMsgType
from ordex.net.messages import MsgVersion, MsgPing, MsgPong

logger = logging.getLogger(__name__)


class NodeConnection:
    """Async TCP connection to a P2P node.

    Usage::

        conn = NodeConnection("127.0.0.1", 25174, chain_params)
        await conn.connect()
        await conn.handshake()
        # ... send/receive messages
        await conn.close()
    """

    def __init__(self, host: str, port: int, chain_params: ChainParams) -> None:
        self.host = host
        self.port = port
        self.params = chain_params
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.peer_version: Optional[MsgVersion] = None
        self._handlers: Dict[str, Callable] = {}
        self._connected = False

    async def connect(self, timeout: float = 10.0) -> None:
        """Establish the TCP connection."""
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            timeout=timeout,
        )
        self._connected = True
        logger.info("Connected to %s:%d", self.host, self.port)

    async def close(self) -> None:
        """Close the connection."""
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self._connected = False
        logger.info("Disconnected from %s:%d", self.host, self.port)

    async def handshake(self, start_height: int = 0) -> None:
        """Perform the version/verack handshake."""
        version_msg = MsgVersion(
            version=self.params.protocol_version,
            start_height=start_height,
        )
        await self.send_message(NetMsgType.VERSION, version_msg.to_bytes())

        # Wait for peer's version
        cmd, payload = await self.recv_message()
        if cmd != NetMsgType.VERSION:
            raise ConnectionError(f"Expected 'version', got '{cmd}'")

        self.peer_version = MsgVersion.deserialize(BytesIO(payload))
        logger.info(
            "Peer version: %d, user_agent: %s, height: %d",
            self.peer_version.version,
            self.peer_version.user_agent,
            self.peer_version.start_height,
        )

        # Send verack
        await self.send_message(NetMsgType.VERACK, b"")

        # Wait for peer's verack
        cmd, payload = await self.recv_message()
        if cmd != NetMsgType.VERACK:
            logger.warning("Expected 'verack', got '%s' — continuing anyway", cmd)

        logger.info("Handshake complete with %s:%d", self.host, self.port)

    async def send_message(self, command: str, payload: bytes) -> None:
        """Send a framed P2P message."""
        if not self.writer:
            raise ConnectionError("Not connected")

        header = CMessageHeader.from_payload(
            self.params.message_start, command, payload
        )
        self.writer.write(header.to_bytes() + payload)
        await self.writer.drain()
        logger.debug("Sent %s (%d bytes)", command, len(payload))

    async def recv_message(self, timeout: float = 30.0) -> tuple[str, bytes]:
        """Receive a framed P2P message.

        Returns (command, payload).
        """
        if not self.reader:
            raise ConnectionError("Not connected")

        # Read header (24 bytes)
        header_data = await asyncio.wait_for(
            self.reader.readexactly(CMessageHeader.HEADER_SIZE),
            timeout=timeout,
        )
        header = CMessageHeader.deserialize(BytesIO(header_data))

        # Verify magic bytes
        if header.message_start != self.params.message_start:
            raise ConnectionError(
                f"Message magic mismatch: {header.message_start.hex()} "
                f"vs expected {self.params.message_start.hex()}"
            )

        # Read payload
        payload = await asyncio.wait_for(
            self.reader.readexactly(header.payload_size),
            timeout=timeout,
        )

        # Verify checksum
        if not header.verify_checksum(payload):
            raise ConnectionError(f"Checksum mismatch for '{header.command}'")

        logger.debug("Received %s (%d bytes)", header.command, len(payload))

        # Auto-respond to pings
        if header.command == NetMsgType.PING:
            ping = MsgPing.deserialize(BytesIO(payload))
            pong = MsgPong(nonce=ping.nonce)
            await self.send_message(NetMsgType.PONG, pong.to_bytes())
            return await self.recv_message(timeout=timeout)

        return header.command, payload

    def register_handler(self, command: str, handler: Callable) -> None:
        """Register a callback for a specific message type."""
        self._handlers[command] = handler

    async def listen(self, timeout: float = 60.0) -> None:
        """Listen for incoming messages and dispatch to handlers.

        Runs until timeout or connection close.
        """
        try:
            while self._connected:
                cmd, payload = await self.recv_message(timeout=timeout)
                handler = self._handlers.get(cmd)
                if handler:
                    await handler(cmd, payload) if asyncio.iscoroutinefunction(handler) else handler(cmd, payload)
                else:
                    logger.debug("Unhandled message: %s (%d bytes)", cmd, len(payload))
        except (asyncio.TimeoutError, ConnectionError, asyncio.IncompleteReadError):
            logger.info("Listen loop ended for %s:%d", self.host, self.port)
