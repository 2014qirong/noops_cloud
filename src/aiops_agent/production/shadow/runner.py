"""Shadow Mode harness runner.

Runs the agent with ``shadow_mode=True`` so high-risk/write side effects are
proposed and recorded but never executed. Safe reads may still run.
Comparisons use human/operator reference cases (recorded SOP fixtures).
"""

from __future__ import annotations

from typing import Any

from aiops_agent.adapters.registry import DEFAULT_REGISTRY, AdapterRegistry
from aiops_agent.production.shadow.cases import SHADOW_SET, ShadowCase
from aiops_agent.production.shadow.compare import compare_to_reference
from aiops_agent.production.shadow.metrics import (
    ShadowCaseResult,
    ShadowMetrics,
    compute_shadow_metrics,
)


def shadow_enabled(env: dict[str, str] | None = None) -> bool:
    """Return True when ``AIOPS_SHADOW_MODE`` is truthy."""
    import os

    source = env if env is not None else os.environ
    return source.get("AIOPS_SHADOW_MODE", "").lower() in {"1", "true", "yes"}


def run_shadow_case(
    case: ShadowCase,
    *,
    registry: AdapterRegistry | None = None,
    max_retries: int = 1,
) -> ShadowCaseResult:
    """Execute one shadow case and compare against the human reference."""
    from aiops_agent.graph.graph import run_agent

    registry = registry or DEFAULT_REGISTRY
    out = run_agent(
        case.input,
        registry=registry,
        hitl_callback=None,  # unused in shadow write path
        max_retries=max_retries,
        shadow_mode=True,
    )
    comparison = compare_to_reference(case, out)
    return ShadowCaseResult(
        case_id=case.id,
        category=case.category,
        agreed=comparison.agreed,
        comparison=comparison,
        tags=list(case.tags),
        agent_output=out,
    )


def run_shadow(
    cases: list[ShadowCase] | None = None,
    *,
    max_retries: int = 1,
) -> tuple[list[ShadowCaseResult], ShadowMetrics]:
    """Run the shadow harness and return (results, metrics)."""
    selected = cases or SHADOW_SET
    results = [run_shadow_case(case, max_retries=max_retries) for case in selected]
    metrics = compute_shadow_metrics(results)
    return results, metrics
