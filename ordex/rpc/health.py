"""
Health Monitor Service for system health and metrics.

Provides health checks, metrics collection, and alerting
for the RPC services.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthState(Enum):
    """Health state."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """Component type."""
    RPC = "rpc"
    DATABASE = "database"
    CACHE = "cache"
    NETWORK = "network"
    WALLET = "wallet"
    BLOCKCHAIN = "blockchain"


@dataclass
class ComponentHealth:
    """Health status of a component."""
    name: str
    component_type: ComponentType
    state: HealthState
    message: str = ""
    latency_ms: float = 0.0
    last_check: Optional[str] = None
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.component_type.value,
            "state": self.state.value,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "last_check": self.last_check,
            "consecutive_failures": self.consecutive_failures,
            "metadata": self.metadata,
        }


@dataclass
class HealthStatus:
    """Overall health status."""
    healthy: bool
    state: HealthState
    components: List[ComponentHealth]
    latency_ms: float = 0.0
    timestamp: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "state": self.state.value,
            "components": [c.to_dict() for c in self.components],
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
            "message": self.message,
        }


@dataclass
class Metric:
    """A metric data point."""
    name: str
    value: float
    timestamp: str
    labels: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels,
        }


@dataclass
class MetricsSummary:
    """Summary of collected metrics."""
    request_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "total_latency_ms": self.total_latency_ms,
            "min_latency_ms": self.min_latency_ms if self.min_latency_ms != float('inf') else 0,
            "max_latency_ms": self.max_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
        }


class HealthMonitor:
    """Health monitoring service.

    Features:
    - Component health checks
    - Metrics collection
    - Alert callbacks
    - Automatic health evaluation
    """

    def __init__(
        self,
        check_interval: int = 30,
        degradation_threshold: int = 3,
        unhealthy_threshold: int = 5,
    ) -> None:
        self._check_interval = check_interval
        self._degradation_threshold = degradation_threshold
        self._unhealthy_threshold = unhealthy_threshold
        self._components: Dict[str, ComponentHealth] = {}
        self._metrics: List[Metric] = []
        self._metrics_lock = threading.Lock()
        self._max_metrics = 10000
        self._lock = threading.Lock()
        self._callbacks: Dict[HealthState, List[Callable]] = {
            HealthState.HEALTHY: [],
            HealthState.DEGRADED: [],
            HealthState.UNHEALTHY: [],
        }
        self._health_check_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._custom_checks: Dict[str, Callable] = {}

    def register_component(
        self,
        name: str,
        component_type: ComponentType,
    ) -> ComponentHealth:
        """Register a component for health monitoring.

        Args:
            name: Component name
            component_type: Type of component

        Returns:
            ComponentHealth instance
        """
        with self._lock:
            health = ComponentHealth(
                name=name,
                component_type=component_type,
                state=HealthState.UNKNOWN,
            )
            self._components[name] = health
            logger.info("Registered component: %s (%s)", name, component_type.value)
            return health

    def unregister_component(self, name: str) -> bool:
        """Unregister a component.

        Args:
            name: Component name

        Returns:
            True if component was removed
        """
        with self._lock:
            if name in self._components:
                del self._components[name]
                return True
            return False

    def update_component(
        self,
        name: str,
        state: HealthState,
        message: str = "",
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update component health status.

        Args:
            name: Component name
            state: New health state
            message: Optional message
            latency_ms: Response latency
            metadata: Additional metadata
        """
        with self._lock:
            if name not in self._components:
                return

            component = self._components[name]

            if state == HealthState.UNHEALTHY:
                component.consecutive_failures += 1
            else:
                component.consecutive_failures = 0

            old_state = component.state
            component.state = state
            component.message = message
            component.latency_ms = latency_ms
            component.last_check = datetime.now(timezone.utc).isoformat()
            if metadata:
                component.metadata.update(metadata)

            if old_state != state:
                logger.warning(
                    "Component %s state changed: %s -> %s",
                    name, old_state.value, state.value
                )
                self._emit_callback(state, component)

    def record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
        """
        with self._metrics_lock:
            metric = Metric(
                name=name,
                value=value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                labels=labels or {},
            )
            self._metrics.append(metric)

            if len(self._metrics) > self._max_metrics:
                self._metrics = self._metrics[-self._max_metrics:]

    def record_request(
        self,
        success: bool,
        latency_ms: float,
    ) -> None:
        """Record an RPC request for metrics.

        Args:
            success: Whether request succeeded
            latency_ms: Request latency
        """
        self.record_metric("rpc_request", 1 if success else 0, {"status": "success" if success else "error"})
        self.record_metric("rpc_latency", latency_ms)

    def get_metrics(self, name: Optional[str] = None) -> List[Metric]:
        """Get collected metrics.

        Args:
            name: Optional filter by metric name

        Returns:
            List of metrics
        """
        with self._metrics_lock:
            if name:
                return [m for m in self._metrics if m.name == name]
            return list(self._metrics)

    def get_metrics_summary(self, name: str = "rpc_latency") -> MetricsSummary:
        """Get summary statistics for a metric.

        Args:
            name: Metric name

        Returns:
            MetricsSummary with statistics
        """
        with self._metrics_lock:
            values = [m.value for m in self._metrics if m.name == name]
            if not values:
                return MetricsSummary()

            summary = MetricsSummary(
                request_count=len(values),
                total_latency_ms=sum(values),
                min_latency_ms=min(values),
                max_latency_ms=max(values),
                avg_latency_ms=sum(values) / len(values),
            )

            sorted_values = sorted(values)
            p95_idx = int(len(sorted_values) * 0.95)
            p99_idx = int(len(sorted_values) * 0.99)
            summary.p95_latency_ms = sorted_values[p95_idx] if sorted_values else 0
            summary.p99_latency_ms = sorted_values[p99_idx] if sorted_values else 0

            error_metrics = [m for m in self._metrics if m.name == "rpc_request" and m.value == 0]
            summary.error_count = len(error_metrics)

            return summary

    def check(self) -> HealthStatus:
        """Get overall health status.

        Returns:
            HealthStatus with all components
        """
        with self._lock:
            components = list(self._components.values())
            start = time.time()

            healthy_count = sum(1 for c in components if c.state == HealthState.HEALTHY)
            degraded_count = sum(1 for c in components if c.state == HealthState.DEGRADED)
            unhealthy_count = sum(1 for c in components if c.state == HealthState.UNHEALTHY)

            if unhealthy_count > 0:
                state = HealthState.UNHEALTHY
                healthy = False
                message = f"{unhealthy_count} component(s) unhealthy"
            elif degraded_count > 0:
                state = HealthState.DEGRADED
                healthy = True
                message = f"{degraded_count} component(s) degraded"
            elif not components:
                state = HealthState.UNKNOWN
                healthy = True
                message = "No components registered"
            else:
                state = HealthState.HEALTHY
                healthy = True
                message = f"{healthy_count} component(s) healthy"

            return HealthStatus(
                healthy=healthy,
                state=state,
                components=components,
                latency_ms=(time.time() - start) * 1000,
                timestamp=datetime.now(timezone.utc).isoformat(),
                message=message,
            )

    def get_component(self, name: str) -> Optional[ComponentHealth]:
        """Get health status of a specific component."""
        with self._lock:
            return self._components.get(name)

    def on_state_change(
        self,
        state: HealthState,
        callback: Callable[[ComponentHealth], None],
    ) -> None:
        """Register a callback for state changes.

        Args:
            state: Health state to listen for
            callback: Function to call on state change
        """
        if state in self._callbacks:
            self._callbacks[state].append(callback)

    def _emit_callback(self, state: HealthState, component: ComponentHealth) -> None:
        """Emit callbacks for state changes."""
        if state in self._callbacks:
            for callback in self._callbacks[state]:
                try:
                    callback(component)
                except Exception as e:
                    logger.error("Health callback error: %s", e)

    def reset_metrics(self) -> None:
        """Clear all collected metrics."""
        with self._metrics_lock:
            self._metrics.clear()

    def summary(self) -> str:
        """Get a human-readable summary."""
        status = self.check()

        lines = [
            "=" * 50,
            "HEALTH MONITOR SUMMARY",
            "=" * 50,
            f"Overall: [{status.state.value.upper()}] {status.message}",
            "",
            "COMPONENTS:",
        ]

        for component in status.components:
            lines.append(
                f"  [{component.state.value.upper()}] {component.name}: {component.message}"
            )

        summary = self.get_metrics_summary("rpc_latency")
        lines.extend([
            "",
            "METRICS:",
            f"  Requests: {summary.request_count}",
            f"  Errors: {summary.error_count}",
            f"  Avg Latency: {summary.avg_latency_ms:.0f}ms",
            f"  P95 Latency: {summary.p95_latency_ms:.0f}ms",
            f"  P99 Latency: {summary.p99_latency_ms:.0f}ms",
            "=" * 50,
        ])

        return "\n".join(lines)