"""Multi-cloud adapter registry — core never hardcodes a single provider."""

from __future__ import annotations

from aiops_agent.adapters.aws import AWSAdapter
from aiops_agent.adapters.azure import AzureAdapter
from aiops_agent.adapters.base import CloudAction, CloudAdapter
from aiops_agent.adapters.gcp import GCPAdapter
from aiops_agent.adapters.k8s import K8sAdapter


class AdapterRegistry:
    """Discovers and routes actions across AWS / Azure / GCP / K8s."""

    def __init__(self, adapters: list[CloudAdapter] | None = None) -> None:
        self._adapters: dict[str, CloudAdapter] = {}
        for adapter in adapters or [
            AWSAdapter(),
            AzureAdapter(),
            GCPAdapter(),
            K8sAdapter(),
        ]:
            self.register(adapter)

    def register(self, adapter: CloudAdapter) -> None:
        self._adapters[adapter.provider] = adapter

    def get(self, provider: str) -> CloudAdapter | None:
        return self._adapters.get(provider)

    def providers(self) -> list[str]:
        return sorted(self._adapters)

    def status(self) -> dict[str, bool]:
        return {name: a.available() for name, a in self._adapters.items()}

    def catalog(self) -> list[dict]:
        items: list[dict] = []
        for provider, adapter in sorted(self._adapters.items()):
            for action in adapter.list_actions():
                items.append(
                    {
                        "provider": provider,
                        "action": action.name,
                        "risk": action.risk.value,
                        "mutating": action.mutating,
                        "description": action.description,
                        "available": adapter.available(),
                    }
                )
        return items

    def resolve(self, provider: str, action_name: str) -> tuple[CloudAdapter, CloudAction]:
        adapter = self.get(provider)
        if adapter is None:
            raise KeyError(f"unknown provider: {provider}")
        action = adapter.get_action(action_name)
        if action is None:
            raise KeyError(f"unknown action {action_name!r} for provider {provider}")
        # merge planner params onto a copy
        return adapter, action


DEFAULT_REGISTRY = AdapterRegistry()
