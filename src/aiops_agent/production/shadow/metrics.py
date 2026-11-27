"""Agreement metrics for Shadow Mode comparison runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiops_agent.production.shadow.compare import ReferenceComparison


@dataclass
class ShadowCaseResult:
    case_id: str
    category: str
    agreed: bool
    comparison: ReferenceComparison
    tags: list[str] = field(default_factory=list)
    agent_output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "agreed": self.agreed,
            "tags": list(self.tags),
            "comparison": self.comparison.to_dict(),
            "disagreements": [
                d.to_dict() for d in self.comparison.diffs if not d.agreed
            ],
        }


@dataclass
class ShadowMetrics:
    total: int = 0
    agreed: int = 0
    disagreed: int = 0
    agreement_rate: float = 0.0
    by_category: dict[str, dict[str, Any]] = field(default_factory=dict)
    provider_agreement: float | None = None
    action_agreement: float | None = None
    risk_agreement: float | None = None
    write_suppress_rate: float | None = None
    read_execute_rate: float | None = None
    disagreement_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "agreed": self.agreed,
            "disagreed": self.disagreed,
            "agreement_rate": self.agreement_rate,
            "by_category": self.by_category,
            "provider_agreement": self.provider_agreement,
            "action_agreement": self.action_agreement,
            "risk_agreement": self.risk_agreement,
            "write_suppress_rate": self.write_suppress_rate,
            "read_execute_rate": self.read_execute_rate,
            "disagreement_count": self.disagreement_count,
        }


def _rate(ok: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(ok / total, 4)


def compute_shadow_metrics(results: list[ShadowCaseResult]) -> ShadowMetrics:
    total = len(results)
    agreed_n = sum(1 for r in results if r.agreed)
    metrics = ShadowMetrics(
        total=total,
        agreed=agreed_n,
        disagreed=total - agreed_n,
        agreement_rate=round(agreed_n / total, 4) if total else 0.0,
    )

    cats: dict[str, list[ShadowCaseResult]] = {}
    for r in results:
        cats.setdefault(r.category, []).append(r)
    metrics.by_category = {
        cat: {
            "total": len(items),
            "agreed": sum(1 for i in items if i.agreed),
            "agreement_rate": _rate(sum(1 for i in items if i.agreed), len(items)),
        }
        for cat, items in sorted(cats.items())
    }

    provider_ok = provider_n = 0
    action_ok = action_n = 0
    risk_ok = risk_n = 0
    disagreement_fields = 0

    for r in results:
        for diff in r.comparison.diffs:
            if not diff.agreed:
                disagreement_fields += 1
            if diff.field == "provider":
                provider_n += 1
                provider_ok += int(diff.agreed)
            elif diff.field == "action":
                action_n += 1
                action_ok += int(diff.agreed)
            elif diff.field == "risk_decision":
                risk_n += 1
                risk_ok += int(diff.agreed)

    write_cases = [r for r in results if r.category == "write"]
    read_cases = [r for r in results if r.category in {"read", "provider"}]
    if write_cases:
        suppressed = sum(1 for r in write_cases if r.comparison.write_suppressed)
        metrics.write_suppress_rate = _rate(suppressed, len(write_cases))
    if read_cases:
        executed = sum(1 for r in read_cases if r.comparison.read_executed)
        metrics.read_execute_rate = _rate(executed, len(read_cases))

    metrics.provider_agreement = _rate(provider_ok, provider_n)
    metrics.action_agreement = _rate(action_ok, action_n)
    metrics.risk_agreement = _rate(risk_ok, risk_n)
    metrics.disagreement_count = disagreement_fields
    return metrics
