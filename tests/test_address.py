"""
Tests for Address Service.
"""

import pytest

from ordex.rpc.address import (
    AddressService,
    AddressInfo,
    AddressDiscoveryResult,
    GapLimitInfo,
    DerivationPath,
    ChainType,
)


class MockRpcClient:
    def __init__(self, addresses=None):
        self._addresses = addresses or {}

    def listunspent(self, minconf, maxconf, addresses):
        result = []
        for addr in addresses:
            if addr in self._addresses:
                result.append({
                    "amount": self._addresses[addr] / 1e8,
                    "txid": "tx123",
                    "vout": 0,
                })
        return result

    def getaddressinfo(self, address):
        return {
            "txcount": len(self._addresses.get(address, [])),
        }


class TestDerivationPath:
    def test_paths(self):
        assert DerivationPath.BIP44.value == "bip44"
        assert DerivationPath.BIP49.value == "bip49"
        assert DerivationPath.BIP84.value == "bip84"


class TestChainType:
    def test_chains(self):
        assert ChainType.EXTERNAL.value == "external"
        assert ChainType.INTERNAL.value == "internal"


class TestAddressInfo:
    def test_to_dict(self):
        info = AddressInfo(
            address="bc1qabc123",
            derivation_path="m/84'/0'/0'/0/0",
            chain=ChainType.EXTERNAL,
            index=0,
            pubkey="pubkey123",
            is_used=True,
            balance=100000,
        )
        data = info.to_dict()
        assert data["address"] == "bc1qabc123"
        assert data["is_used"] is True
        assert data["balance"] == 100000


class TestAddressDiscoveryResult:
    def test_to_dict(self):
        result = AddressDiscoveryResult(
            found_addresses=["addr1", "addr2"],
            unused_external_count=5,
            unused_internal_count=3,
            last_used_external=10,
            last_used_internal=8,
            scanned_count=100,
        )
        data = result.to_dict()
        assert len(data["found_addresses"]) == 2
        assert data["scanned_count"] == 100


class TestGapLimitInfo:
    def test_to_dict(self):
        info = GapLimitInfo(
            wallet_id="wallet1",
            last_used_external=15,
            last_used_internal=10,
            gap_limit=20,
            is_synced=True,
        )
        data = info.to_dict()
        assert data["wallet_id"] == "wallet1"
        assert data["is_synced"] is True


class TestAddressService:
    def test_init(self):
        service = AddressService()
        assert service._rpc_client is None
        assert service._gap_limit == 20

    def test_init_with_params(self):
        service = AddressService(gap_limit=50)
        assert service._gap_limit == 50

    def test_set_rpc_client(self):
        service = AddressService()
        rpc = MockRpcClient()
        service.set_rpc_client(rpc)
        assert service._rpc_client is rpc

    def test_set_wallet_manager(self):
        service = AddressService()
        service.set_wallet_manager("manager")
        assert service._wallet_manager == "manager"


class TestAddressServiceGenerate:
    def test_generate_single(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1)
        assert len(addresses) == 1
        assert addresses[0]

    def test_generate_multiple(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=5)
        assert len(addresses) == 5

    def test_generate_internal_chain(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1, chain=ChainType.INTERNAL)
        assert len(addresses) == 1

    def test_generate_bip44(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1, derivation=DerivationPath.BIP44)
        assert len(addresses) == 1
        info = service.get_address_info(addresses[0])
        assert info is not None

    def test_generate_bip49(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1, derivation=DerivationPath.BIP49)
        assert len(addresses) == 1

    def test_generate_bip84(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1, derivation=DerivationPath.BIP84)
        assert len(addresses) == 1

    def test_generate_multiple_wallets(self):
        service = AddressService()
        service.generate("wallet1", count=3)
        service.generate("wallet2", count=2)
        assert service.get_address_count("wallet1") == 3
        assert service.get_address_count("wallet2") == 2

    def test_on_address_generated_callback(self):
        service = AddressService()
        results = []
        service.on_address_generated(lambda info: results.append(info))
        service.generate("wallet1", count=2)
        assert len(results) == 2


class TestAddressServiceValidation:
    def test_validate_p2pkh(self):
        service = AddressService()
        assert service.validate("1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2") is True

    def test_validate_p2sh(self):
        service = AddressService()
        assert service.validate("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") is True

    def test_validate_bech32(self):
        service = AddressService()
        assert service.validate("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4") is True

    def test_validate_invalid(self):
        service = AddressService()
        assert service.validate("") is False
        assert service.validate("invalid") is False
        assert service.validate("0" * 100) is False

    def test_validate_short(self):
        service = AddressService()
        assert service.validate("abc") is False


class TestAddressServiceBalance:
    def test_get_balance_no_rpc(self):
        service = AddressService()
        balance = service.get_balance("bc1qabc123")
        assert balance == 0

    def test_get_balance_with_rpc(self):
        rpc = MockRpcClient({"addr1": 50000})
        service = AddressService(rpc_client=rpc)
        balance = service.get_balance("addr1")
        assert balance == 50000

    def test_get_balance_no_balance(self):
        rpc = MockRpcClient()
        service = AddressService(rpc_client=rpc)
        balance = service.get_balance("addr1")
        assert balance == 0


class TestAddressServiceTransactionCount:
    def test_get_transaction_count_no_rpc(self):
        service = AddressService()
        count = service.get_transaction_count("bc1qabc123")
        assert count == 0

    def test_get_transaction_count_with_rpc(self):
        rpc = MockRpcClient({"addr1": 100000})
        service = AddressService(rpc_client=rpc)
        count = service.get_transaction_count("addr1")
        assert count == 0


class TestAddressServiceMarkUsed:
    def test_mark_used(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1)
        address = addresses[0]
        service.mark_used(address)
        info = service.get_address_info(address)
        assert info.is_used is True

    def test_on_address_used_callback(self):
        service = AddressService()
        results = []
        service.on_address_used(lambda info: results.append(info))
        addresses = service.generate("wallet1", count=1)
        service.mark_used(addresses[0])
        assert len(results) == 1


class TestAddressServiceImport:
    def test_import_valid_address(self):
        service = AddressService()
        assert service.import_address("wallet1", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4") is True
        assert service.get_address_count("wallet1") == 1

    def test_import_with_label(self):
        service = AddressService()
        service.import_address("wallet1", "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4", label="My Address")
        info = service.get_address_info("bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4")
        assert info.label == "My Address"

    def test_import_invalid_address(self):
        service = AddressService()
        assert service.import_address("wallet1", "invalid") is False


class TestAddressServiceGapLimit:
    def test_get_gap_info(self):
        service = AddressService(gap_limit=25)
        info = service.get_gap_info("wallet1")
        assert info.wallet_id == "wallet1"
        assert info.gap_limit == 25

    def test_update_gap_info(self):
        service = AddressService()
        service.update_gap_info("wallet1", last_used_external=10, last_used_internal=5)
        info = service.get_gap_info("wallet1")
        assert info.last_used_external == 10
        assert info.last_used_internal == 5
        assert info.is_synced is True


class TestAddressServiceDiscovery:
    def test_discover_no_gap(self):
        service = AddressService(gap_limit=5)
        service.set_rpc_client(MockRpcClient())
        result = service.discover("wallet1", gap_limit=5)
        assert result.scanned_count > 0


class TestAddressServiceDerivation:
    def test_get_derivation(self):
        service = AddressService()
        addresses = service.generate("wallet1", count=1)
        derivation = service.get_derivation(addresses[0])
        assert derivation is not None
        assert "path" in derivation
        assert "chain" in derivation

    def test_get_derivation_not_found(self):
        service = AddressService()
        derivation = service.get_derivation("bc1qnotfound")
        assert derivation is None


class TestAddressServiceWalletAddresses:
    def test_get_wallet_addresses(self):
        service = AddressService()
        service.generate("wallet1", count=3)
        addresses = service.get_wallet_addresses("wallet1")
        assert len(addresses) == 3

    def test_get_wallet_addresses_empty(self):
        service = AddressService()
        addresses = service.get_wallet_addresses("nonexistent")
        assert len(addresses) == 0

    def test_get_address_count(self):
        service = AddressService()
        service.generate("wallet1", count=5)
        assert service.get_address_count("wallet1") == 5