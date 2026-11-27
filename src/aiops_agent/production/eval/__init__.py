"""Golden-set evaluation harness (deterministic; no cloud creds / paid LLM)."""

from aiops_agent.production.eval.cases import GOLDEN_SET, GoldenCase, get_case
from aiops_agent.production.eval.metrics import CaseResult, EvalMetrics, compute_metrics
from aiops_agent.production.eval.report import write_report
from aiops_agent.production.eval.runner import run_case, run_eval, run_golden_set

__all__ = [
    "GOLDEN_SET",
    "GoldenCase",
    "CaseResult",
    "EvalMetrics",
    "compute_metrics",
    "get_case",
    "run_case",
    "run_eval",
    "run_golden_set",
    "write_report",
]
