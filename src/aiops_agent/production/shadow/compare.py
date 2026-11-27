"""Compare agent shadow proposals against human/operator reference actions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aiops_agent.production.shadow.cases import ShadowCase


# Decision fields used by the legacy prod-vs-candidate helper.
_LEGACY_KEYS = ("provider", "action", "risk_decision", "is_fallback", "blocked")


@dataclass
class ShadowComparison:
    """Result of comparing two decision dicts (legacy prod vs candidate)."""

    prompt: str
    production: dict[str, Any]
    candidate: dict[str, Any]
    diverged: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "production": self.production,
            "candidate": self.candidate,
            "diverged": self.diverged,
            "notes": list(self.notes),
        }


@dataclass
class FieldDiff:
    field: str
    reference: Any
    proposed: Any
    agreed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "reference": self.reference,
            "proposed": self.proposed,
            "agreed": self.agreed,
        }


@dataclass
class ReferenceComparison:
    """Agent proposal vs human/operator reference for one shadow case."""

    case_id: str
    prompt: str
    reference: dict[str, Any]
    proposal: dict[str, Any]
    agreed: bool
    diffs: list[FieldDiff] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    write_suppressed: bool = False
    read_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "prompt": self.prompt,
            "reference": self.reference,
            "proposal": self.proposal,
            "agreed": self.agreed,
            "diffs": [d.to_dict() for d in self.diffs],
            "notes": list(self.notes),
            "write_suppressed": self.write_suppressed,
            "read_executed": self.read_executed,
        }


def compare_shadow(
    prompt: str,
    production: dict[str, Any],
    candidate: dict[str, Any],
) -> ShadowComparison:
    """Diff key decision fields between production and candidate outputs.

    Kept for backward compatibility with the original stub API.
    """
    notes: list[str] = []
    diverged = False
    for key in _LEGACY_KEYS:
        pv = production.get(key)
        cv = candidate.get(key)
        if pv != cv:
            diverged = True
            notes.append(f"{key}: prod={pv!r} candidate={cv!r}")
    return ShadowComparison(
        prompt=prompt,
        production=production,
        candidate=candidate,
        diverged=diverged,
        notes=notes,
    )


def extract_proposal(agent_out: dict[str, Any]) -> dict[str, Any]:
    """Normalize agent run output into a comparable proposal dict."""
    plan = agent_out.get("plan") or {}
    provider = agent_out.get("provider") or plan.get("provider")
    action = agent_out.get("action") or plan.get("action")
    params = agent_out.get("action_params") or plan.get("params") or {}
    exec_result = agent_out.get("execution_result") or {}
    risk = agent_out.get("risk_decision")
    # After shadow suppress, risk_decision stays "hitl"; blocked → reject.
    if agent_out.get("blocked"):
        risk = risk or "reject"
    return {
        "provider": provider,
        "action": action,
        "params": params,
        "risk_decision": risk,
        "blocked": bool(agent_out.get("blocked")),
        "is_fallback": bool(agent_out.get("is_fallback")),
        "hitl_required": bool(agent_out.get("hitl_required")),
        "shadow_proposed": bool(agent_out.get("shadow_proposed")),
        "shadow_suppressed": bool(agent_out.get("shadow_suppressed")),
        "execution_mode": exec_result.get("mode"),
        "execution_ok": (exec_result.get("ok") if "ok" in exec_result else None),
        "stub": exec_result.get("stub"),
    }


def compare_to_reference(
    case: ShadowCase,
    agent_out: dict[str, Any],
) -> ReferenceComparison:
    """Score agent shadow proposal against the human/operator reference."""
    proposal = extract_proposal(agent_out)
    reference: dict[str, Any] = {
        "provider": case.reference_provider,
        "action": case.reference_action,
        "risk_decision": case.reference_risk_decision,
        "blocked": case.reference_blocked,
        "params_contains": case.reference_params_contains,
    }
    diffs: list[FieldDiff] = []
    notes: list[str] = []

    def _check(field: str, ref_val: Any, proposed_val: Any, *, soft: bool = False) -> bool:
        if ref_val is None:
            return True
        if soft and isinstance(ref_val, str) and proposed_val is not None:
            ok = ref_val in str(proposed_val)
        else:
            ok = ref_val == proposed_val
        diffs.append(
            FieldDiff(field=field, reference=ref_val, proposed=proposed_val, agreed=ok)
        )
        if not ok:
            notes.append(f"{field}: reference={ref_val!r} proposed={proposed_val!r}")
        return ok

    agreed = True
    agreed &= _check("provider", case.reference_provider, proposal.get("provider"))
    agreed &= _check(
        "action",
        case.reference_action,
        proposal.get("action"),
        soft=True,
    )
    agreed &= _check(
        "risk_decision",
        case.reference_risk_decision,
        proposal.get("risk_decision"),
    )
    agreed &= _check("blocked", case.reference_blocked, proposal.get("blocked"))

    if case.reference_params_contains:
        params = proposal.get("params") or {}
        missing = {
            k: v
            for k, v in case.reference_params_contains.items()
            if params.get(k) != v
        }
        ok = not missing
        diffs.append(
            FieldDiff(
                field="params_contains",
                reference=case.reference_params_contains,
                proposed=params,
                agreed=ok,
            )
        )
        if not ok:
            notes.append(f"params_contains mismatch: missing/wrong={missing!r}")
            agreed = False

    write_suppressed = bool(proposal.get("shadow_suppressed"))
    read_executed = (
        proposal.get("execution_mode") != "shadow"
        and proposal.get("risk_decision") == "execute"
        and not proposal.get("blocked")
        and proposal.get("execution_ok") is True
    )

    if case.expect_write_suppressed is True and not write_suppressed:
        notes.append("expected write to be suppressed in shadow mode")
        agreed = False
        diffs.append(
            FieldDiff(
                field="write_suppressed",
                reference=True,
                proposed=write_suppressed,
                agreed=False,
            )
        )
    elif case.expect_write_suppressed is False and write_suppressed:
        # Soft: only flag if we explicitly expected no suppress
        notes.append("write unexpectedly suppressed")
        agreed = False

    if case.expect_read_executed is True and not read_executed:
        notes.append("expected safe read to execute in shadow mode")
        agreed = False
        diffs.append(
            FieldDiff(
                field="read_executed",
                reference=True,
                proposed=read_executed,
                agreed=False,
            )
        )

    return ReferenceComparison(
        case_id=case.id,
        prompt=case.input,
        reference=reference,
        proposal=proposal,
        agreed=agreed,
        diffs=diffs,
        notes=notes,
        write_suppressed=write_suppressed,
        read_executed=read_executed,
    )
