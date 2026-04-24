"""
Notification Service for event system, webhooks, and callbacks.

Features:
- Event registration and dispatching
- Webhook delivery with HMAC signatures
- Retry logic for failed webhooks
- Event filtering
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types for notifications."""
    WALLET_BALANCE_CHANGED = "wallet.balance_changed"
    WALLET_UTXO_SPENT = "wallet.utxo.spent"
    WALLET_UTXO_CREATED = "wallet.utxo.created"
    TX_NEW = "tx.new"
    TX_CONFIRMED = "tx.confirmed"
    TX_REPLACED = "tx.replaced"
    TX_FAILED = "tx.failed"
    BLOCK_NEW = "block.new"
    BLOCK_REORG = "block.reorg"


@dataclass
class Event:
    """An event notification."""
    event_type: str
    data: Dict[str, Any]
    timestamp: str = ""
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "event_id": self.event_id,
        }


@dataclass
class WebhookConfig:
    """Webhook configuration."""
    webhook_id: str
    url: str
    events: List[str]
    secret: str
    enabled: bool = True
    retry_count: int = 3
    retry_delay: float = 1.0
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "webhook_id": self.webhook_id,
            "url": self.url,
            "events": self.events,
            "secret": "***" if self.secret else "",
            "enabled": self.enabled,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
        }


@dataclass
class WebhookDelivery:
    """Webhook delivery record."""
    webhook_id: str
    event_id: str
    success: bool
    status_code: int = 0
    response_body: str = ""
    duration_ms: float = 0.0
    attempt: int = 1
    error: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "webhook_id": self.webhook_id,
            "event_id": self.event_id,
            "success": self.success,
            "status_code": self.status_code,
            "response_body": self.response_body[:200] if self.response_body else "",
            "duration_ms": self.duration_ms,
            "attempt": self.attempt,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class EventBus:
    """In-process event bus for callback notifications."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000

    def register(self, event: str, callback: Callable[[Event], None]) -> None:
        """Register a handler for an event.

        Args:
            event: Event name
            callback: Function receiving Event
        """
        with self._lock:
            if event not in self._handlers:
                self._handlers[event] = []
            self._handlers[event].append(callback)

    def unregister(self, event: str, callback: Callable) -> bool:
        """Unregister a handler.

        Args:
            event: Event name
            callback: Handler to remove

        Returns:
            True if handler was found and removed
        """
        with self._lock:
            if event in self._handlers:
                try:
                    self._handlers[event].remove(callback)
                    return True
                except ValueError:
                    pass
            return False

    def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: Event to emit
        """
        with self._lock:
            handlers = self._handlers.get(event.event_type, [])
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error("Event handler error for %s: %s", event.event_type, e)

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get event history.

        Args:
            event_type: Filter by event type
            limit: Maximum events to return

        Returns:
            List of events
        """
        with self._lock:
            history = self._event_history
            if event_type:
                history = [e for e in history if e.event_type == event_type]
            return list(history[-limit:])


class NotificationService:
    """Notification service for events and webhooks.

    Features:
    - Event registration
    - Webhook management
    - HMAC signatures
    - Retry logic
    - Event filtering
    """

    def __init__(self, http_client: Optional[Any] = None) -> None:
        self._http_client = http_client
        self._lock = threading.Lock()
        self._event_bus = EventBus()
        self._webhooks: Dict[str, WebhookConfig] = {}
        self._delivery_history: List[WebhookDelivery] = []
        self._max_delivery_history = 5000
        self._webhook_id_counter = 0
        self._enabled = True

    def set_http_client(self, http_client: Any) -> None:
        """Set HTTP client for webhook delivery."""
        self._http_client = http_client

    def register(
        self,
        event: str,
        callback: Callable[[Event], None],
    ) -> None:
        """Register a callback for an event.

        Args:
            event: Event name
            callback: Function receiving Event
        """
        self._event_bus.register(event, callback)

    def unregister(self, event: str, callback: Callable) -> bool:
        """Unregister a callback.

        Args:
            event: Event name
            callback: Handler to remove

        Returns:
            True if handler was removed
        """
        return self._event_bus.unregister(event, callback)

    def emit(
        self,
        event_type: str,
        data: Dict[str, Any],
        event_id: Optional[str] = None,
    ) -> Event:
        """Emit an event.

        Args:
            event_type: Type of event
            data: Event data
            event_id: Optional event ID

        Returns:
            Created Event
        """
        if not self._enabled:
            return Event(event_type=event_type, data=data)

        event = Event(
            event_type=event_type,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_id=event_id or self._generate_event_id(),
        )

        self._event_bus.emit(event)
        self._dispatch_webhooks(event)

        return event

    def _dispatch_webhooks(self, event: Event) -> None:
        """Dispatch event to matching webhooks."""
        with self._lock:
            matching_webhooks = [
                wh for wh in self._webhooks.values()
                if wh.enabled and event.event_type in wh.events
            ]

        for webhook in matching_webhooks:
            self._deliver_webhook_async(webhook, event)

    def _deliver_webhook_async(self, webhook: WebhookConfig, event: Event) -> None:
        """Deliver webhook asynchronously."""
        thread = threading.Thread(
            target=self._deliver_webhook,
            args=(webhook, event),
            daemon=True,
        )
        thread.start()

    def _deliver_webhook(
        self,
        webhook: WebhookConfig,
        event: Event,
    ) -> WebhookDelivery:
        """Deliver a webhook with retry logic."""
        payload = json.dumps(event.to_dict())
        signature = self._generate_signature(payload, webhook.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-ID": webhook.webhook_id,
            "X-Event-ID": event.event_id,
        }

        delivery = WebhookDelivery(
            webhook_id=webhook.webhook_id,
            event_id=event.event_id,
            success=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        for attempt in range(webhook.retry_count):
            delivery.attempt = attempt + 1
            start_time = time.time()

            try:
                if self._http_client:
                    response = self._http_client.post(
                        webhook.url,
                        data=payload,
                        headers=headers,
                        timeout=30,
                    )
                    delivery.status_code = response.status_code
                    delivery.response_body = response.text
                    delivery.success = 200 <= response.status_code < 300
                else:
                    delivery.success = True
                    delivery.status_code = 200

                delivery.duration_ms = (time.time() - start_time) * 1000

                if delivery.success:
                    break

            except Exception as e:
                delivery.error = str(e)
                delivery.duration_ms = (time.time() - start_time) * 1000
                logger.error("Webhook delivery error: %s", e)

            if attempt < webhook.retry_count - 1:
                time.sleep(webhook.retry_delay)

        with self._lock:
            self._delivery_history.append(delivery)
            if len(self._delivery_history) > self._max_delivery_history:
                self._delivery_history = self._delivery_history[-self._max_delivery_history:]

        return delivery

    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for payload."""
        if not secret:
            return ""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        timestamp = str(time.time()).encode()
        return hashlib.sha256(timestamp).hexdigest()[:16]

    def add_webhook(
        self,
        url: str,
        events: List[str],
        secret: str = "",
        retry_count: int = 3,
        retry_delay: float = 1.0,
    ) -> str:
        """Add a webhook configuration.

        Args:
            url: Webhook URL
            events: List of event types to subscribe
            secret: HMAC secret for signatures
            retry_count: Number of retry attempts
            retry_delay: Delay between retries

        Returns:
            Webhook ID
        """
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Invalid webhook URL")

        with self._lock:
            self._webhook_id_counter += 1
            webhook_id = f"wh_{self._webhook_id_counter:06d}"

            webhook = WebhookConfig(
                webhook_id=webhook_id,
                url=url,
                events=events,
                secret=secret,
                retry_count=retry_count,
                retry_delay=retry_delay,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            self._webhooks[webhook_id] = webhook
            logger.info("Added webhook: %s for events: %s", webhook_id, events)

            return webhook_id

    def remove_webhook(self, webhook_id: str) -> bool:
        """Remove a webhook.

        Args:
            webhook_id: Webhook ID to remove

        Returns:
            True if webhook was found and removed
        """
        with self._lock:
            if webhook_id in self._webhooks:
                del self._webhooks[webhook_id]
                logger.info("Removed webhook: %s", webhook_id)
                return True
            return False

    def enable_webhook(self, webhook_id: str) -> bool:
        """Enable a webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            True if webhook was found
        """
        with self._lock:
            if webhook_id in self._webhooks:
                self._webhooks[webhook_id].enabled = True
                return True
            return False

    def disable_webhook(self, webhook_id: str) -> bool:
        """Disable a webhook.

        Args:
            webhook_id: Webhook ID

        Returns:
            True if webhook was found
        """
        with self._lock:
            if webhook_id in self._webhooks:
                self._webhooks[webhook_id].enabled = False
                return True
            return False

    def get_webhook(self, webhook_id: str) -> Optional[WebhookConfig]:
        """Get webhook configuration.

        Args:
            webhook_id: Webhook ID

        Returns:
            WebhookConfig or None
        """
        with self._lock:
            return self._webhooks.get(webhook_id)

    def list_webhooks(self) -> List[WebhookConfig]:
        """List all webhooks.

        Returns:
            List of webhook configurations
        """
        with self._lock:
            return list(self._webhooks.values())

    def get_delivery_history(
        self,
        webhook_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[WebhookDelivery]:
        """Get webhook delivery history.

        Args:
            webhook_id: Filter by webhook ID
            limit: Maximum records

        Returns:
            List of delivery records
        """
        with self._lock:
            history = self._delivery_history
            if webhook_id:
                history = [d for d in history if d.webhook_id == webhook_id]
            return list(history[-limit:])

    def get_event_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Event]:
        """Get event history.

        Args:
            event_type: Filter by event type
            limit: Maximum events

        Returns:
            List of events
        """
        return self._event_bus.get_history(event_type, limit)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the notification service.

        Args:
            enabled: Enable/disable state
        """
        self._enabled = enabled

    def clear_history(self) -> None:
        """Clear event and delivery history."""
        with self._lock:
            self._delivery_history.clear()
            self._event_bus._event_history.clear()