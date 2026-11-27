"""Output guardrails: conclusion + evidence chain, light hallucination checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    step: str
    provider: str | None = None
    action: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    ok: bool = True


@dataclass
class OutputPayload:
    conclusion: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    is_fallback: bool = False
    hitl_required: bool = False
    hitl_approved: bool | None = None
    blocked: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "evidence": [
                {
                    "step": e.step,
                    "provider": e.provider,
                    "action": e.action,
                    "detail": e.detail,
                    "ok": e.ok,
                }
                for e in self.evidence
            ],
            "is_fallback": self.is_fallback,
            "hitl_required": self.hitl_required,
            "hitl_approved": self.hitl_approved,
            "blocked": self.blocked,
            "warnings": self.warnings,
        }


def check_hallucination(
    conclusion: str,
    evidence: list[EvidenceItem],
) -> list[str]:
    """Flag conclusions that claim success without supporting evidence."""
    warnings: list[str] = []
    success_words = ("resolved", "fixed", "mitigated", "success", "completed")
    lower = conclusion.lower()
    claims_success = any(w in lower for w in success_words)
    if claims_success and not evidence:
        warnings.append("conclusion claims success but evidence chain is empty")
    if claims_success and evidence and not any(e.ok for e in evidence):
        warnings.append("conclusion claims success but all evidence steps failed")
    # provider/action names in conclusion should appear in evidence when present
    for e in evidence:
        if e.action and e.action in conclusion and not e.ok:
            warnings.append(f"conclusion references failed action {e.action}")
    return warnings


def build_output(
    conclusion: str,
    evidence: list[EvidenceItem],
    *,
    is_fallback: bool = False,
    hitl_required: bool = False,
    hitl_approved: bool | None = None,
    blocked: bool = False,
) -> OutputPayload:
    warnings = check_hallucination(conclusion, evidence)
    return OutputPayload(
        conclusion=conclusion,
        evidence=evidence,
        is_fallback=is_fallback,
        hitl_required=hitl_required,
        hitl_approved=hitl_approved,
        blocked=blocked,
        warnings=warnings,
    )
