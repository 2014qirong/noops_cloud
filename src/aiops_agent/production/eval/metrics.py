"""Aggregate metrics for golden-set evaluation runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiops_agent.production.eval.cases import GoldenCase


@dataclass
class CaseResult:
    case_id: str
    category: str
    passed: bool
    checks: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "passed": self.passed,
            "checks": self.checks,
            "failures": self.failures,
            "tags": list(self.tags),
            "output_summary": {
                "blocked": self.output.get("blocked"),
                "provider": self.output.get("provider"),
                "action": self.output.get("action"),
                "risk_decision": self.output.get("risk_decision"),
                "is_fallback": self.output.get("is_fallback"),
                "hitl_required": self.output.get("hitl_required"),
                "hitl_approved": self.output.get("hitl_approved"),
                "retry_count": self.output.get("retry_count"),
                "execution_ok": (self.output.get("execution_result") or {}).get("ok"),
            },
        }


@dataclass
class EvalMetrics:
    total: int = 0
    passed: int = 0
    failed: int = 0
    pass_rate: float = 0.0
    by_category: dict[str, dict[str, Any]] = field(default_factory=dict)
    provider_accuracy: float | None = None
    hitl_correctness: float | None = None
    risk_correctness: float | None = None
    fallback_correctness: float | None = None
    guardrail_true_positives: int = 0
    guardrail_false_negatives: int = 0
    guardrail_true_negatives: int = 0
    guardrail_false_positives: int = 0
    guardrail_precision: float | None = None
    guardrail_recall: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "by_category": self.by_category,
            "provider_accuracy": self.provider_accuracy,
            "hitl_correctness": self.hitl_correctness,
            "risk_correctness": self.risk_correctness,
            "fallback_correctness": self.fallback_correctness,
            "guardrail": {
                "true_positives": self.guardrail_true_positives,
                "false_negatives": self.guardrail_false_negatives,
                "true_negatives": self.guardrail_true_negatives,
                "false_positives": self.guardrail_false_positives,
                "precision": self.guardrail_precision,
                "recall": self.guardrail_recall,
            },
        }


def _rate(ok: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(ok / total, 4)


def compute_metrics(
    results: list[CaseResult],
    cases: list[GoldenCase] | None = None,
) -> EvalMetrics:
    """Derive pass rate and specialized correctness metrics from case results."""
    case_map = {c.id: c for c in (cases or [])}
    total = len(results)
    passed_n = sum(1 for r in results if r.passed)
    metrics = EvalMetrics(
        total=total,
        passed=passed_n,
        failed=total - passed_n,
        pass_rate=round(passed_n / total, 4) if total else 0.0,
    )

    cats: dict[str, list[CaseResult]] = {}
    for r in results:
        cats.setdefault(r.category, []).append(r)
    metrics.by_category = {
        cat: {
            "total": len(items),
            "passed": sum(1 for i in items if i.passed),
            "pass_rate": _rate(sum(1 for i in items if i.passed), len(items)),
        }
        for cat, items in sorted(cats.items())
    }

    provider_ok = provider_n = 0
    hitl_ok = hitl_n = 0
    risk_ok = risk_n = 0
    fallback_ok = fallback_n = 0

    for r in results:
        case = case_map.get(r.case_id)
        if case is None:
            continue
        if case.expect_provider is not None:
            provider_n += 1
            if r.checks.get("provider_ok") is True:
                provider_ok += 1
        if case.expect_hitl is not None:
            hitl_n += 1
            if r.checks.get("hitl_ok") is True:
                hitl_ok += 1
        if case.expect_risk_decision is not None:
            risk_n += 1
            if r.checks.get("risk_ok") is True:
                risk_ok += 1
        if case.expect_fallback is not None:
            fallback_n += 1
            if r.checks.get("fallback_ok") is True:
                fallback_ok += 1

        is_guardrail = (
            case.category == "guardrail"
            or "injection" in case.tags
            or "false_positive_check" in case.tags
        )
        if is_guardrail and case.expect_blocked is not None:
            actual_blocked = bool(r.output.get("blocked"))
            if case.expect_blocked:
                if actual_blocked:
                    metrics.guardrail_true_positives += 1
                else:
                    metrics.guardrail_false_negatives += 1
            else:
                if actual_blocked:
                    metrics.guardrail_false_positives += 1
                else:
                    metrics.guardrail_true_negatives += 1

    metrics.provider_accuracy = _rate(provider_ok, provider_n)
    metrics.hitl_correctness = _rate(hitl_ok, hitl_n)
    metrics.risk_correctness = _rate(risk_ok, risk_n)
    metrics.fallback_correctness = _rate(fallback_ok, fallback_n)

    tp = metrics.guardrail_true_positives
    fp = metrics.guardrail_false_positives
    fn = metrics.guardrail_false_negatives
    metrics.guardrail_precision = _rate(tp, tp + fp) if (tp + fp) else None
    metrics.guardrail_recall = _rate(tp, tp + fn) if (tp + fn) else None

    return metrics
