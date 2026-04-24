"""
Tests for Health Monitor Service.
"""

import time
from datetime import datetime, timezone
import pytest

from ordex.rpc.health import (
    HealthMonitor,
    HealthState,
    ComponentType,
    ComponentHealth,
    HealthStatus,
    Metric,
    MetricsSummary,
)


class TestComponentHealth:
    def test_to_dict(self):
        health = ComponentHealth(
            name="test-component",
            component_type=ComponentType.RPC,
            state=HealthState.HEALTHY,
            message="All good",
            latency_ms=10.5,
            last_check="2024-01-01T00:00:00Z",
            consecutive_failures=0,
        )
        data = health.to_dict()
        assert data["name"] == "test-component"
        assert data["type"] == "rpc"
        assert data["state"] == "healthy"
        assert data["message"] == "All good"
        assert data["latency_ms"] == 10.5
        assert data["consecutive_failures"] == 0


class TestHealthStatus:
    def test_to_dict(self):
        component = ComponentHealth(
            name="test",
            component_type=ComponentType.RPC,
            state=HealthState.HEALTHY,
        )
        status = HealthStatus(
            healthy=True,
            state=HealthState.HEALTHY,
            components=[component],
            latency_ms=5.0,
            timestamp="2024-01-01T00:00:00Z",
            message="All healthy",
        )
        data = status.to_dict()
        assert data["healthy"] is True
        assert data["state"] == "healthy"
        assert len(data["components"]) == 1


class TestMetric:
    def test_to_dict(self):
        metric = Metric(
            name="test_metric",
            value=100.0,
            timestamp="2024-01-01T00:00:00Z",
            labels={"env": "test"},
        )
        data = metric.to_dict()
        assert data["name"] == "test_metric"
        assert data["value"] == 100.0
        assert data["labels"]["env"] == "test"


class TestMetricsSummary:
    def test_to_dict_empty(self):
        summary = MetricsSummary()
        data = summary.to_dict()
        assert data["request_count"] == 0
        assert data["error_count"] == 0
        assert data["min_latency_ms"] == 0

    def test_to_dict_with_values(self):
        summary = MetricsSummary(
            request_count=100,
            error_count=5,
            total_latency_ms=1000.0,
            min_latency_ms=5.0,
            max_latency_ms=50.0,
            avg_latency_ms=10.0,
            p95_latency_ms=25.0,
            p99_latency_ms=40.0,
        )
        data = summary.to_dict()
        assert data["request_count"] == 100
        assert data["error_count"] == 5
        assert data["avg_latency_ms"] == 10.0


class TestHealthMonitor:
    def test_init(self):
        monitor = HealthMonitor(check_interval=60, degradation_threshold=5)
        assert monitor._check_interval == 60
        assert monitor._degradation_threshold == 5
        assert len(monitor._components) == 0

    def test_register_component(self):
        monitor = HealthMonitor()
        health = monitor.register_component("test-service", ComponentType.RPC)
        assert health.name == "test-service"
        assert health.component_type == ComponentType.RPC
        assert health.state == HealthState.UNKNOWN

    def test_register_duplicate_component(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        health = monitor.register_component("test-service", ComponentType.RPC)
        assert health.name == "test-service"

    def test_unregister_component(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        assert monitor.unregister_component("test-service") is True
        assert monitor.unregister_component("nonexistent") is False

    def test_unregister_nonexistent(self):
        monitor = HealthMonitor()
        assert monitor.unregister_component("nonexistent") is False

    def test_update_component(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        monitor.update_component(
            "test-service",
            state=HealthState.HEALTHY,
            message="Running fine",
            latency_ms=15.0,
        )
        component = monitor.get_component("test-service")
        assert component.state == HealthState.HEALTHY
        assert component.message == "Running fine"
        assert component.latency_ms == 15.0
        assert component.consecutive_failures == 0

    def test_update_component_consecutive_failures(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        monitor.update_component("test-service", state=HealthState.UNHEALTHY)
        assert monitor.get_component("test-service").consecutive_failures == 1
        monitor.update_component("test-service", state=HealthState.UNHEALTHY)
        assert monitor.get_component("test-service").consecutive_failures == 2
        monitor.update_component("test-service", state=HealthState.HEALTHY)
        assert monitor.get_component("test-service").consecutive_failures == 0

    def test_update_component_state_change_callback(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        state_changes = []

        def callback(component):
            state_changes.append(component.state)

        monitor.on_state_change(HealthState.HEALTHY, callback)
        monitor.update_component("test-service", state=HealthState.HEALTHY)
        assert len(state_changes) == 1
        assert state_changes[0] == HealthState.HEALTHY

    def test_update_nonexistent_component(self):
        monitor = HealthMonitor()
        monitor.update_component("nonexistent", state=HealthState.HEALTHY)

    def test_update_component_with_metadata(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        monitor.update_component(
            "test-service",
            state=HealthState.HEALTHY,
            metadata={"version": "1.0.0", "region": "us-west"},
        )
        component = monitor.get_component("test-service")
        assert component.metadata["version"] == "1.0.0"
        assert component.metadata["region"] == "us-west"

    def test_get_component(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        component = monitor.get_component("test-service")
        assert component is not None
        assert component.name == "test-service"

    def test_get_component_nonexistent(self):
        monitor = HealthMonitor()
        assert monitor.get_component("nonexistent") is None


class TestHealthMonitorCheck:
    def test_check_no_components(self):
        monitor = HealthMonitor()
        status = monitor.check()
        assert status.state == HealthState.UNKNOWN
        assert status.healthy is True
        assert len(status.components) == 0

    def test_check_all_healthy(self):
        monitor = HealthMonitor()
        monitor.register_component("service-a", ComponentType.RPC)
        monitor.register_component("service-b", ComponentType.RPC)
        monitor.update_component("service-a", state=HealthState.HEALTHY)
        monitor.update_component("service-b", state=HealthState.HEALTHY)
        status = monitor.check()
        assert status.state == HealthState.HEALTHY
        assert status.healthy is True

    def test_check_degraded(self):
        monitor = HealthMonitor()
        monitor.register_component("service-a", ComponentType.RPC)
        monitor.register_component("service-b", ComponentType.RPC)
        monitor.update_component("service-a", state=HealthState.HEALTHY)
        monitor.update_component("service-b", state=HealthState.DEGRADED)
        status = monitor.check()
        assert status.state == HealthState.DEGRADED
        assert status.healthy is True

    def test_check_unhealthy(self):
        monitor = HealthMonitor()
        monitor.register_component("service-a", ComponentType.RPC)
        monitor.register_component("service-b", ComponentType.RPC)
        monitor.update_component("service-a", state=HealthState.UNHEALTHY)
        monitor.update_component("service-b", state=HealthState.HEALTHY)
        status = monitor.check()
        assert status.state == HealthState.UNHEALTHY
        assert status.healthy is False


class TestHealthMonitorMetrics:
    def test_record_metric(self):
        monitor = HealthMonitor()
        monitor.record_metric("request_count", 1.0)
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "request_count"
        assert metrics[0].value == 1.0

    def test_record_metric_with_labels(self):
        monitor = HealthMonitor()
        monitor.record_metric("request_count", 1.0, {"endpoint": "/api/health"})
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].labels["endpoint"] == "/api/health"

    def test_get_metrics_filtered(self):
        monitor = HealthMonitor()
        monitor.record_metric("metric_a", 1.0)
        monitor.record_metric("metric_b", 2.0)
        monitor.record_metric("metric_a", 3.0)
        metrics = monitor.get_metrics("metric_a")
        assert len(metrics) == 2
        assert all(m.name == "metric_a" for m in metrics)

    def test_record_request_success(self):
        monitor = HealthMonitor()
        monitor.record_request(success=True, latency_ms=50.0)
        metrics = monitor.get_metrics("rpc_request")
        assert len(metrics) == 1
        assert metrics[0].value == 1.0

    def test_record_request_failure(self):
        monitor = HealthMonitor()
        monitor.record_request(success=False, latency_ms=100.0)
        metrics = monitor.get_metrics("rpc_request")
        assert len(metrics) == 1
        assert metrics[0].value == 0.0

    def test_get_metrics_summary_empty(self):
        monitor = HealthMonitor()
        summary = monitor.get_metrics_summary("rpc_latency")
        assert summary.request_count == 0
        assert summary.error_count == 0

    def test_get_metrics_summary_with_data(self):
        monitor = HealthMonitor()
        monitor.record_request(success=True, latency_ms=10.0)
        monitor.record_request(success=True, latency_ms=20.0)
        monitor.record_request(success=True, latency_ms=30.0)
        monitor.record_request(success=False, latency_ms=100.0)
        summary = monitor.get_metrics_summary("rpc_latency")
        assert summary.request_count == 4
        assert summary.error_count == 1
        assert summary.min_latency_ms == 10.0
        assert summary.max_latency_ms == 100.0
        assert summary.avg_latency_ms == 40.0

    def test_get_metrics_summary_percentiles(self):
        monitor = HealthMonitor()
        for i in range(100):
            monitor.record_request(success=True, latency_ms=float(i + 1))
        summary = monitor.get_metrics_summary("rpc_latency")
        assert summary.p95_latency_ms == 96.0
        assert summary.p99_latency_ms == 100.0

    def test_reset_metrics(self):
        monitor = HealthMonitor()
        monitor.record_metric("test_metric", 1.0)
        monitor.record_metric("test_metric", 2.0)
        assert len(monitor.get_metrics()) == 2
        monitor.reset_metrics()
        assert len(monitor.get_metrics()) == 0


class TestHealthMonitorCallbacks:
    def test_on_state_change_multiple(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        results = []

        def callback1(component):
            results.append("callback1")

        def callback2(component):
            results.append("callback2")

        monitor.on_state_change(HealthState.HEALTHY, callback1)
        monitor.on_state_change(HealthState.HEALTHY, callback2)
        monitor.update_component("test-service", state=HealthState.HEALTHY)
        assert len(results) == 2
        assert "callback1" in results
        assert "callback2" in results

    def test_callback_exception_handling(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)

        def failing_callback(component):
            raise ValueError("Test error")

        monitor.on_state_change(HealthState.HEALTHY, failing_callback)
        monitor.update_component("test-service", state=HealthState.HEALTHY)

    def test_callback_not_called_for_same_state(self):
        monitor = HealthMonitor()
        monitor.register_component("test-service", ComponentType.RPC)
        state_changes = []

        def callback(component):
            state_changes.append(component.state)

        monitor.on_state_change(HealthState.HEALTHY, callback)
        monitor.update_component("test-service", state=HealthState.HEALTHY)
        monitor.update_component("test-service", state=HealthState.HEALTHY)
        assert len(state_changes) == 1


class TestHealthMonitorSummary:
    def test_summary(self):
        monitor = HealthMonitor()
        monitor.register_component("service-a", ComponentType.RPC)
        monitor.register_component("service-b", ComponentType.RPC)
        monitor.update_component("service-a", state=HealthState.HEALTHY, message="OK")
        monitor.update_component("service-b", state=HealthState.DEGRADED, message="Slow")
        summary = monitor.summary()
        assert "HEALTH MONITOR SUMMARY" in summary
        assert "service-a" in summary
        assert "service-b" in summary
        assert "DEGRADED" in summary
        assert "Avg Latency" in summary


class TestComponentType:
    def test_component_types(self):
        assert ComponentType.RPC.value == "rpc"
        assert ComponentType.DATABASE.value == "database"
        assert ComponentType.CACHE.value == "cache"
        assert ComponentType.NETWORK.value == "network"
        assert ComponentType.WALLET.value == "wallet"
        assert ComponentType.BLOCKCHAIN.value == "blockchain"


class TestHealthState:
    def test_health_states(self):
        assert HealthState.HEALTHY.value == "healthy"
        assert HealthState.DEGRADED.value == "degraded"
        assert HealthState.UNHEALTHY.value == "unhealthy"
        assert HealthState.UNKNOWN.value == "unknown"