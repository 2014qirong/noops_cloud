"""Backward-compatible exports for the golden-set eval harness.

The real implementation lives under ``aiops_agent.production.eval``.
This module keeps the historical import path used by CLI and early tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from aiops_agent.production.eval.cases import GOLDEN_SET, GoldenCase

__all__ = [
    "GOLDEN_SET",
    "GoldenCase",
    "EvalResult",
    "run_golden_set",
]


@dataclass
class EvalResult:
    """Legacy result shape returned when callers pass a custom ``runner``."""

    case_id: str
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)


def run_golden_set(
    runner: Callable[[str], dict[str, Any]] | None = None,
    cases: list[GoldenCase] | None = None,
) -> list[Any]:
    """Delegate to the full harness (lazy import avoids graph cycles)."""
    from aiops_agent.production.eval.runner import run_golden_set as _run

    return _run(runner=runner, cases=cases)
