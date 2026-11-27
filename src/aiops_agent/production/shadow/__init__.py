"""Shadow Mode — propose actions, suppress high-risk writes, compare to SOP."""

from aiops_agent.production.shadow.cases import (
    SHADOW_SET,
    ShadowCase,
    get_shadow_case,
    shadow_cases_by_category,
)
from aiops_agent.production.shadow.compare import (
    ReferenceComparison,
    ShadowComparison,
    compare_shadow,
    compare_to_reference,
    extract_proposal,
)
from aiops_agent.production.shadow.metrics import (
    ShadowCaseResult,
    ShadowMetrics,
    compute_shadow_metrics,
)
from aiops_agent.production.shadow.report import write_shadow_report
from aiops_agent.production.shadow.runner import run_shadow, run_shadow_case, shadow_enabled

__all__ = [
    "SHADOW_SET",
    "ShadowCase",
    "ShadowCaseResult",
    "ShadowComparison",
    "ShadowMetrics",
    "ReferenceComparison",
    "compare_shadow",
    "compare_to_reference",
    "compute_shadow_metrics",
    "extract_proposal",
    "get_shadow_case",
    "run_shadow",
    "run_shadow_case",
    "shadow_cases_by_category",
    "shadow_enabled",
    "write_shadow_report",
]
