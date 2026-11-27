"""Multi-cloud provider adapters (AWS / Azure / GCP / K8s)."""

from aiops_agent.adapters.base import ActionResult, ActionRisk, CloudAction, CloudAdapter
from aiops_agent.adapters.registry import AdapterRegistry, DEFAULT_REGISTRY

__all__ = [
    "ActionResult",
    "ActionRisk",
    "CloudAction",
    "CloudAdapter",
    "AdapterRegistry",
    "DEFAULT_REGISTRY",
]
