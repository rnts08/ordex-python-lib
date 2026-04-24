"""
Tests for unified RPC services container.
"""

import pytest

from ordex.rpc.services import (
    OrdexServices,
    OrdexConfig,
)


class MockRpcClient:
    def __init__(self):
        self._calls = []

    def __getattr__(self, name):
        self._calls.append(name)
        return lambda *args, **kwargs: {}


class MockNodePool:
    def __init__(self, nodes=None):
        self._nodes = nodes or []
        self._client = MockRpcClient()

    def get_client(self):
        return self._client

    def get_healthy_nodes(self):
        return [{"url": "http://localhost:8332"}]


class TestOrdexConfig:
    def test_default_config(self):
        config = OrdexConfig()
        assert config.nodes == []
        assert config.check_interval == 30
        assert config.gap_limit == 20

    def test_custom_config(self):
        config = OrdexConfig(
            nodes=[{"url": "http://localhost:8332"}],
            rpc_user="user",
            rpc_password="pass",
            check_interval=60,
            gap_limit=50,
        )
        assert len(config.nodes) == 1
        assert config.check_interval == 60
        assert config.gap_limit == 50


class TestOrdexServices:
    def test_init(self):
        services = OrdexServices()
        assert services._config is not None
        assert services._initialized is False

    def test_init_with_config(self):
        config = OrdexConfig(nodes=[{"url": "http://localhost:8332"}])
        services = OrdexServices(config)
        assert services._config.nodes[0]["url"] == "http://localhost:8332"


class TestOrdexServicesInitialize:
    def test_initialize_lazy(self):
        services = OrdexServices()
        services.initialize()
        assert services._initialized is True

    def test_initialize_twice(self):
        services = OrdexServices()
        services.initialize()
        services.initialize()
        assert services._initialized is True


class TestOrdexServicesProperties:
    def test_network_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.network is not None

    def test_health_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.health is not None

    def test_mempool_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.mempool is not None

    def test_blocks_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.blocks is not None

    def test_address_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.address is not None

    def test_transactions_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.transactions is not None

    def test_tracker_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.tracker is not None

    def test_notifications_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.notifications is not None


class TestOrdexServicesHealth:
    def test_check_health(self):
        services = OrdexServices()
        services.initialize()
        health = services.check_health()
        assert isinstance(health, dict)
        assert "network" in health
        assert "health" in health


class TestOrdexServicesStats:
    def test_get_stats(self):
        services = OrdexServices()
        services.initialize()
        stats = services.get_stats()
        assert isinstance(stats, dict)
        assert "tracked_transactions" in stats
        assert "mempool_size" in stats
        assert "block_height" in stats


class TestOrdexServicesShutdown:
    def test_shutdown(self):
        services = OrdexServices()
        services.initialize()
        services.shutdown()
        assert services._initialized is False


class TestOrdexServicesPrivateClient:
    def test_rpc_client_property(self):
        services = OrdexServices()
        services.initialize()
        assert services.rpc_client is not None


class TestCreateServices:
    def test_create_services_factory(self):
        from ordex.rpc.services import create_services

        services = create_services([{"url": "http://localhost:8332"}])
        assert services._initialized is True
        assert services._config.nodes[0]["url"] == "http://localhost:8332"


class TestOrdexServicesModuleExports:
    def test_module_version(self):
        from ordex.rpc import __version__
        assert __version__ == "1.1.0"

    def test_module_exports(self):
        from ordex.rpc import OrdexServices, OrdexConfig, create_services
        assert OrdexServices is not None
        assert OrdexConfig is not None
        assert create_services is not None