"""Rule-based planner — selects provider + action without single-cloud bias.

Uses keyword heuristics so the loop runs without an LLM API key.
Swap `plan_actions` for an LLM chain later; the graph contract stays stable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from aiops_agent.adapters.registry import AdapterRegistry, DEFAULT_REGISTRY


@dataclass
class Plan:
    provider: str
    action: str
    params: dict[str, Any]
    rationale: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "action": self.action,
            "params": self.params,
            "rationale": self.rationale,
            "confidence": self.confidence,
        }


_PROVIDER_HINTS: list[tuple[str, list[str]]] = [
    ("aws", ["aws", "cloudwatch", "ecs", "asg", "ec2", "alb"]),
    ("azure", ["azure", "app service", "aks vm", "microsoft cloud"]),
    ("gcp", ["gcp", "gke", "cloud monitoring", "mig", "google cloud"]),
    ("k8s", ["k8s", "kubernetes", "pod", "deployment", "namespace", "kubectl", "crashloop"]),
]


def _detect_provider(text: str) -> str:
    lower = text.lower()
    scores: dict[str, int] = {}
    for provider, hints in _PROVIDER_HINTS:
        scores[provider] = sum(1 for h in hints if h in lower)
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] == 0:
        return "k8s"  # default ops surface when unspecified
    return best


def _extract_name(text: str, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        m = re.search(rf"(?i)\b{key}\s+([a-zA-Z0-9][\w.-]*)", text)
        if m:
            return m.group(1)
    return None


def plan_actions(
    text: str,
    *,
    registry: AdapterRegistry | None = None,
    error_context: str | None = None,
) -> Plan:
    """Produce a single next action from natural-language ops intent."""
    registry = registry or DEFAULT_REGISTRY
    lower = text.lower()
    if error_context:
        lower = f"{lower} | prior_error: {error_context.lower()}"

    provider = _detect_provider(lower)
    namespace = _extract_name(text, ("namespace", "ns")) or "default"
    deployment = _extract_name(text, ("deployment", "deploy", "service", "svc"))
    params: dict[str, Any] = {"namespace": namespace}
    if deployment:
        params["name"] = deployment

    # Mutating intents first
    if any(w in lower for w in ("restart", "rollout restart", "recycle")):
        if provider == "aws":
            return Plan("aws", "restart_ecs_service", {"cluster": "default", "service": deployment or "api"}, "restart intent → ECS", 0.8)
        if provider == "azure":
            return Plan("azure", "restart_vm", {"resource_group": "rg", "vm_name": deployment or "app-vm"}, "restart intent → VM", 0.75)
        if provider == "gcp":
            return Plan(
                "gcp",
                "restart_gke_deployment",
                {"namespace": namespace, "deployment": deployment or "api"},
                "restart intent → GKE",
                0.8,
            )
        return Plan("k8s", "restart_deployment", params | {"name": deployment or "api"}, "restart intent → Deployment", 0.85)

    if any(w in lower for w in ("scale", "replicas", "capacity")):
        if provider == "aws":
            return Plan("aws", "scale_asg", {"asg": deployment or "web-asg", "desired": 2}, "scale intent → ASG", 0.8)
        if provider == "azure":
            return Plan("azure", "scale_app_service", {"plan": "prod-plan", "instances": 2}, "scale intent → App Service", 0.75)
        if provider == "gcp":
            return Plan("gcp", "resize_mig", {"mig": deployment or "web-mig", "size": 2}, "scale intent → MIG", 0.75)
        return Plan(
            "k8s",
            "scale_deployment",
            params | {"name": deployment or "api", "replicas": 2},
            "scale intent → Deployment",
            0.85,
        )

    if "delete" in lower and "pod" in lower:
        pod = _extract_name(text, ("pod",)) or "api-7d9f"
        return Plan("k8s", "delete_pod", {"namespace": namespace, "name": pod}, "delete pod intent", 0.9)

    # Read intents
    if provider == "aws":
        if "alarm" in lower:
            return Plan("aws", "describe_alarms", {}, "CloudWatch alarms", 0.9)
        return Plan("aws", "get_metric_stats", {"namespace": "AWS/EC2", "metric": "CPUUtilization"}, "AWS metrics", 0.7)

    if provider == "azure":
        if "alert" in lower:
            return Plan("azure", "list_alerts", {}, "Azure alerts", 0.9)
        return Plan("azure", "get_metrics", {"metric": "Percentage CPU"}, "Azure metrics", 0.7)

    if provider == "gcp":
        if "incident" in lower:
            return Plan("gcp", "list_incidents", {}, "GCP incidents", 0.9)
        return Plan("gcp", "query_timeseries", {}, "GCP timeseries", 0.7)

    # k8s reads
    if any(w in lower for w in ("event", "warning", "backoff")):
        return Plan("k8s", "get_events", {"namespace": namespace}, "K8s events", 0.85)
    if "deployment" in lower and any(w in lower for w in ("describe", "status", "show")):
        return Plan("k8s", "describe_deployment", params | {"name": deployment or "api"}, "describe deployment", 0.85)
    return Plan("k8s", "get_pods", {"namespace": namespace}, "default: inspect pods", 0.7)
