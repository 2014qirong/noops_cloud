"""Production hardening scaffolding (timeouts, budget, tracing, eval, shadow)."""

# Keep imports lightweight: do not pull eval.runner (→ graph) at package import time.
from aiops_agent.production.eval.cases import GOLDEN_SET, GoldenCase
from aiops_agent.production.eval_stub import EvalResult, run_golden_set
from aiops_agent.production.shadow import compare_shadow, shadow_enabled
from aiops_agent.production.timeouts import TimeoutPolicy, maybe_switch_model
from aiops_agent.production.token_budget import ResponseCache, TokenBudget
from aiops_agent.production.tracing import InMemoryTracer, NoOpTracer

__all__ = [
    "GOLDEN_SET",
    "GoldenCase",
    "EvalResult",
    "run_golden_set",
    "run_eval",
    "write_report",
    "compare_shadow",
    "shadow_enabled",
    "TimeoutPolicy",
    "maybe_switch_model",
    "ResponseCache",
    "TokenBudget",
    "InMemoryTracer",
    "NoOpTracer",
]


def __getattr__(name: str):
    """Lazy exports that would otherwise create import cycles with the graph."""
    if name == "run_eval":
        from aiops_agent.production.eval.runner import run_eval

        return run_eval
    if name == "write_report":
        from aiops_agent.production.eval.report import write_report

        return write_report
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
