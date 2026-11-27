"""Production hardening scaffolding (timeouts, budget, tracing, eval, shadow)."""

from aiops_agent.production.eval_stub import GOLDEN_SET, run_golden_set
from aiops_agent.production.shadow import compare_shadow, shadow_enabled
from aiops_agent.production.timeouts import TimeoutPolicy, maybe_switch_model
from aiops_agent.production.token_budget import ResponseCache, TokenBudget
from aiops_agent.production.tracing import InMemoryTracer, NoOpTracer

__all__ = [
    "GOLDEN_SET",
    "run_golden_set",
    "compare_shadow",
    "shadow_enabled",
    "TimeoutPolicy",
    "maybe_switch_model",
    "ResponseCache",
    "TokenBudget",
    "InMemoryTracer",
    "NoOpTracer",
]
