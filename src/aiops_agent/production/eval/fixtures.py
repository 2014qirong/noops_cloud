"""Deterministic adapter fixtures for observer / failure golden cases.

No cloud credentials or paid APIs — adapters fail or recover in-memory.
"""

from __future__ import annotations

from aiops_agent.adapters.base import ActionResult, ActionRisk, CloudAction, CloudAdapter
from aiops_agent.adapters.registry import AdapterRegistry


class FlakyK8sAdapter(CloudAdapter):
    """Fails once, then succeeds — exercises Observer retry + error_context."""

    provider = "k8s"

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    def list_actions(self) -> list[CloudAction]:
        return [
            CloudAction(name="get_pods", risk=ActionRisk.READ, params={"namespace": "default"}),
            CloudAction(name="get_events", risk=ActionRisk.READ, params={"namespace": "default"}),
            CloudAction(
                name="describe_deployment",
                risk=ActionRisk.LOW,
                params={"namespace": "default", "name": "api"},
            ),
        ]

    def execute(self, action: CloudAction) -> ActionResult:
        self.calls += 1
        if self.calls == 1:
            return ActionResult(
                ok=False,
                provider=self.provider,
                action=action.name,
                error="temporary API timeout",
                stub=True,
            )
        return ActionResult(
            ok=True,
            provider=self.provider,
            action=action.name,
            data={"pods": [], "recovered": True, "calls": self.calls},
            stub=True,
        )


class AlwaysFailK8sAdapter(CloudAdapter):
    """Always fails — exercises retry exhaustion → fallback/circuit-break."""

    provider = "k8s"

    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    def list_actions(self) -> list[CloudAction]:
        return [
            CloudAction(name="get_pods", risk=ActionRisk.READ, params={"namespace": "default"}),
            CloudAction(name="get_events", risk=ActionRisk.READ, params={"namespace": "default"}),
        ]

    def execute(self, action: CloudAction) -> ActionResult:
        self.calls += 1
        return ActionResult(
            ok=False,
            provider=self.provider,
            action=action.name,
            error=f"persistent API failure (call={self.calls})",
            stub=True,
        )


def build_fixture_registry(name: str) -> AdapterRegistry:
    """Return a registry containing only the named fixture adapter."""
    if name == "flaky_k8s":
        return AdapterRegistry(adapters=[FlakyK8sAdapter()])
    if name == "always_fail_k8s":
        return AdapterRegistry(adapters=[AlwaysFailK8sAdapter()])
    raise KeyError(f"unknown eval fixture: {name!r}")
