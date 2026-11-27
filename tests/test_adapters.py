from aiops_agent.adapters.aws import AWSAdapter
from aiops_agent.adapters.azure import AzureAdapter
from aiops_agent.adapters.gcp import GCPAdapter
from aiops_agent.adapters.k8s import K8sAdapter
from aiops_agent.adapters.registry import AdapterRegistry


def test_registry_has_four_providers():
    reg = AdapterRegistry()
    assert set(reg.providers()) == {"aws", "azure", "gcp", "k8s"}


def test_stub_execute_without_credentials():
    for adapter_cls in (AWSAdapter, AzureAdapter, GCPAdapter, K8sAdapter):
        adapter = adapter_cls()
        actions = adapter.list_actions()
        assert actions
        read = next(a for a in actions if not a.mutating)
        result = adapter.execute(read)
        assert result.ok
        assert result.stub is True or adapter.available()


def test_catalog_entries_include_risk():
    catalog = AdapterRegistry().catalog()
    assert len(catalog) >= 8
    assert all("provider" in c and "risk" in c for c in catalog)
