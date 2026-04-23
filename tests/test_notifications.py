"""
Tests for Notification Service.
"""

import json
import pytest
from unittest.mock import Mock

from ordex.rpc.notifications import (
    NotificationService,
    EventBus,
    Event,
    EventType,
    WebhookConfig,
    WebhookDelivery,
)


class MockHttpClient:
    def __init__(self, success=True, status_code=200):
        self._success = success
        self._status_code = status_code
        self._requests = []

    def post(self, url, data=None, headers=None, timeout=None):
        self._requests.append({"url": url, "data": data, "headers": headers})
        response = Mock()
        response.status_code = self._status_code
        response.text = "OK" if self._success else "Error"
        return response


class TestEventType:
    def test_event_types(self):
        assert EventType.WALLET_BALANCE_CHANGED.value == "wallet.balance_changed"
        assert EventType.TX_NEW.value == "tx.new"
        assert EventType.BLOCK_NEW.value == "block.new"


class TestEvent:
    def test_to_dict(self):
        event = Event(
            event_type="tx.new",
            data={"txid": "abc123"},
            timestamp="2024-01-01T00:00:00Z",
            event_id="evt123",
        )
        data = event.to_dict()
        assert data["event_type"] == "tx.new"
        assert data["data"]["txid"] == "abc123"
        assert data["event_id"] == "evt123"


class TestWebhookConfig:
    def test_to_dict(self):
        config = WebhookConfig(
            webhook_id="wh_001",
            url="https://example.com/webhook",
            events=["tx.new"],
            secret="secret123",
        )
        data = config.to_dict()
        assert data["webhook_id"] == "wh_001"
        assert data["secret"] == "***"


class TestWebhookDelivery:
    def test_to_dict(self):
        delivery = WebhookDelivery(
            webhook_id="wh_001",
            event_id="evt123",
            success=True,
            status_code=200,
            duration_ms=50.0,
        )
        data = delivery.to_dict()
        assert data["success"] is True
        assert data["duration_ms"] == 50.0


class TestEventBus:
    def test_register(self):
        bus = EventBus()
        handler_called = []

        def handler(event):
            handler_called.append(event)

        bus.register("tx.new", handler)
        bus.emit(Event(event_type="tx.new", data={}))
        assert len(handler_called) == 1

    def test_unregister(self):
        bus = EventBus()
        handler_called = []

        def handler(event):
            handler_called.append(event)

        bus.register("tx.new", handler)
        bus.unregister("tx.new", handler)
        bus.emit(Event(event_type="tx.new", data={}))
        assert len(handler_called) == 0

    def test_unregister_not_found(self):
        bus = EventBus()
        result = bus.unregister("tx.new", lambda e: None)
        assert result is False

    def test_emit_multiple_handlers(self):
        bus = EventBus()
        results = []

        bus.register("tx.new", lambda e: results.append(1))
        bus.register("tx.new", lambda e: results.append(2))
        bus.emit(Event(event_type="tx.new", data={}))
        assert len(results) == 2

    def test_get_history(self):
        bus = EventBus()
        for i in range(5):
            bus.emit(Event(event_type="tx.new", data={"i": i}))
        history = bus.get_history(limit=3)
        assert len(history) == 3

    def test_get_history_filtered(self):
        bus = EventBus()
        bus.emit(Event(event_type="tx.new", data={}))
        bus.emit(Event(event_type="tx.confirmed", data={}))
        history = bus.get_history(event_type="tx.new")
        assert len(history) == 1
        assert history[0].event_type == "tx.new"


class TestNotificationService:
    def test_init(self):
        service = NotificationService()
        assert service._enabled is True

    def test_set_http_client(self):
        service = NotificationService()
        client = MockHttpClient()
        service.set_http_client(client)
        assert service._http_client is client


class TestNotificationServiceEvents:
    def test_register(self):
        service = NotificationService()
        results = []
        service.register("tx.new", lambda e: results.append(e))
        service.emit("tx.new", {"txid": "abc123"})
        assert len(results) == 1

    def test_unregister(self):
        service = NotificationService()
        handler = lambda e: None
        service.register("tx.new", handler)
        result = service.unregister("tx.new", handler)
        assert result is True

    def test_emit(self):
        service = NotificationService()
        results = []
        service.register("tx.new", lambda e: results.append(e))
        event = service.emit("tx.new", {"txid": "abc123"})
        assert event.event_type == "tx.new"
        assert len(results) == 1

    def test_emit_disabled(self):
        service = NotificationService()
        service.set_enabled(False)
        results = []
        service.register("tx.new", lambda e: results.append(e))
        service.emit("tx.new", {"txid": "abc123"})
        assert len(results) == 0

    def test_emit_generates_event_id(self):
        service = NotificationService()
        event = service.emit("tx.new", {})
        assert len(event.event_id) > 0


class TestNotificationServiceWebhooks:
    def test_add_webhook(self):
        service = NotificationService()
        webhook_id = service.add_webhook(
            "https://example.com/webhook",
            ["tx.new"],
            secret="secret123",
        )
        assert webhook_id.startswith("wh_")
        webhook = service.get_webhook(webhook_id)
        assert webhook is not None
        assert webhook.secret == "secret123"

    def test_add_webhook_invalid_url(self):
        service = NotificationService()
        with pytest.raises(ValueError):
            service.add_webhook("not-a-url", ["tx.new"])

    def test_remove_webhook(self):
        service = NotificationService()
        webhook_id = service.add_webhook("https://example.com/webhook", ["tx.new"])
        assert service.remove_webhook(webhook_id) is True
        assert service.get_webhook(webhook_id) is None

    def test_remove_webhook_not_found(self):
        service = NotificationService()
        assert service.remove_webhook("nonexistent") is False

    def test_enable_webhook(self):
        service = NotificationService()
        webhook_id = service.add_webhook("https://example.com/webhook", ["tx.new"])
        service.disable_webhook(webhook_id)
        assert service.enable_webhook(webhook_id) is True
        assert service.get_webhook(webhook_id).enabled is True

    def test_disable_webhook(self):
        service = NotificationService()
        webhook_id = service.add_webhook("https://example.com/webhook", ["tx.new"])
        assert service.disable_webhook(webhook_id) is True
        assert service.get_webhook(webhook_id).enabled is False

    def test_list_webhooks(self):
        service = NotificationService()
        service.add_webhook("https://example1.com/webhook", ["tx.new"])
        service.add_webhook("https://example2.com/webhook", ["tx.confirmed"])
        webhooks = service.list_webhooks()
        assert len(webhooks) == 2


class TestNotificationServiceDelivery:
    def test_webhook_delivery(self):
        client = MockHttpClient(success=True)
        service = NotificationService(http_client=client)
        webhook_id = service.add_webhook(
            "https://example.com/webhook",
            ["tx.new"],
            secret="secret123",
        )
        service.emit("tx.new", {"txid": "abc123"})
        history = service.get_delivery_history(webhook_id=webhook_id)
        assert len(history) >= 1

    def test_webhook_delivery_with_retry(self):
        client = MockHttpClient(success=True)
        service = NotificationService(http_client=client)
        service.add_webhook(
            "https://example.com/webhook",
            ["tx.new"],
            retry_count=2,
        )
        service.emit("tx.new", {"txid": "abc123"})

    def test_get_delivery_history(self):
        client = MockHttpClient(success=True)
        service = NotificationService(http_client=client)
        service.add_webhook("https://example.com/webhook", ["tx.new"])
        service.emit("tx.new", {"txid": "abc123"})
        history = service.get_delivery_history(limit=10)
        assert len(history) >= 1


class TestNotificationServiceHistory:
    def test_get_event_history(self):
        service = NotificationService()
        service.emit("tx.new", {"txid": "1"})
        service.emit("tx.confirmed", {"txid": "2"})
        history = service.get_event_history()
        assert len(history) == 2

    def test_get_event_history_filtered(self):
        service = NotificationService()
        service.emit("tx.new", {"txid": "1"})
        service.emit("tx.confirmed", {"txid": "2"})
        history = service.get_event_history(event_type="tx.new")
        assert len(history) == 1


class TestNotificationServiceClear:
    def test_clear_history(self):
        service = NotificationService()
        service.emit("tx.new", {"txid": "1"})
        service.clear_history()
        history = service.get_event_history()
        assert len(history) == 0


class TestNotificationServiceEventTypes:
    def test_emit_wallet_balance_changed(self):
        service = NotificationService()
        results = []
        service.register(EventType.WALLET_BALANCE_CHANGED.value, lambda e: results.append(e))
        service.emit(
            EventType.WALLET_BALANCE_CHANGED.value,
            {"wallet_id": "wallet1", "old_balance": 1000, "new_balance": 2000},
        )
        assert len(results) == 1

    def test_emit_block_reorg(self):
        service = NotificationService()
        results = []
        service.register(EventType.BLOCK_REORG.value, lambda e: results.append(e))
        service.emit(
            EventType.BLOCK_REORG.value,
            {"old_height": 100, "new_height": 101},
        )
        assert len(results) == 1