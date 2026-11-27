"""LangGraph node functions for the AIOps closed loop."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable

from aiops_agent.adapters.base import CloudAction
from aiops_agent.adapters.registry import AdapterRegistry, DEFAULT_REGISTRY
from aiops_agent.graph.planner import plan_actions
from aiops_agent.graph.state import AgentState
from aiops_agent.guardrails.input_guard import apply_input_guardrails
from aiops_agent.guardrails.output_guard import EvidenceItem, build_output
from aiops_agent.risk.gate import RiskDecision, assess_risk


HitlCallback = Callable[[dict[str, Any]], bool]


def _append_evidence(state: AgentState, item: EvidenceItem) -> list[dict[str, Any]]:
    evidence = list(state.get("evidence") or [])
    evidence.append(
        {
            "step": item.step,
            "provider": item.provider,
            "action": item.action,
            "detail": item.detail,
            "ok": item.ok,
        }
    )
    return evidence


def input_guard_node(state: AgentState) -> dict[str, Any]:
    raw = state.get("raw_input") or ""
    if state.get("error_context"):
        # Observer retry: fold error context into the next planning input.
        raw = f"{raw}\n\n[error_context]\n{state['error_context']}"
    result = apply_input_guardrails(raw)
    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="input_guard",
            detail={
                "redactions": result.redactions,
                "injection_detected": result.injection_detected,
                "matches": result.injection_matches,
            },
            ok=not result.blocked,
        ),
    )
    out: dict[str, Any] = {
        "sanitized_input": result.sanitized,
        "injection_detected": result.injection_detected,
        "blocked": result.blocked,
        "block_reason": result.reason,
        "redactions": result.redactions,
        "evidence": evidence,
        "should_retry": False,
    }
    if result.blocked:
        out["is_fallback"] = True
        out["risk_decision"] = RiskDecision.REJECT.value
        out["conclusion"] = f"Blocked by input guardrails: {result.reason}"
    return out


def planner_node(
    state: AgentState,
    *,
    registry: AdapterRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or DEFAULT_REGISTRY
    text = state.get("sanitized_input") or state.get("raw_input") or ""
    plan = plan_actions(
        text,
        registry=registry,
        error_context=state.get("error_context"),
    )
    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="planner",
            provider=plan.provider,
            action=plan.action,
            detail=plan.to_dict(),
            ok=True,
        ),
    )
    return {
        "plan": plan.to_dict(),
        "provider": plan.provider,
        "action": plan.action,
        "action_params": plan.params,
        "evidence": evidence,
    }


def risk_gate_node(
    state: AgentState,
    *,
    registry: AdapterRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or DEFAULT_REGISTRY
    provider = state.get("provider")
    action_name = state.get("action")
    cloud_action: CloudAction | None = None
    if provider and action_name:
        adapter = registry.get(provider)
        if adapter:
            found = adapter.get_action(action_name)
            if found:
                # overlay planner params
                cloud_action = replace(found, params={**found.params, **(state.get("action_params") or {})})

    verdict = assess_risk(cloud_action)
    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="risk_gate",
            provider=provider,
            action=action_name,
            detail={"decision": verdict.decision.value, "reason": verdict.reason},
            ok=verdict.decision != RiskDecision.REJECT,
        ),
    )
    return {
        "risk_decision": verdict.decision.value,
        "risk_reason": verdict.reason,
        "risk_level": verdict.risk.value,
        "requires_hitl": verdict.requires_hitl,
        "is_fallback": verdict.is_fallback,
        "evidence": evidence,
    }


def hitl_node(state: AgentState) -> dict[str, Any]:
    """Human-in-the-loop approval for high-risk writes.

    Uses optional `hitl_callback` on state; defaults to deny (safe).
    """
    callback: HitlCallback | None = state.get("hitl_callback")
    payload = {
        "provider": state.get("provider"),
        "action": state.get("action"),
        "params": state.get("action_params") or {},
        "risk_reason": state.get("risk_reason"),
    }
    approved = False
    if callable(callback):
        approved = bool(callback(payload))
    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="hitl",
            provider=state.get("provider"),
            action=state.get("action"),
            detail={"approved": approved, "payload": payload},
            ok=approved,
        ),
    )
    updates: dict[str, Any] = {
        "hitl_approved": approved,
        "evidence": evidence,
    }
    if not approved:
        updates["is_fallback"] = True
        updates["risk_decision"] = RiskDecision.FALLBACK.value
        updates["risk_reason"] = "HITL denied or no approver configured"
    return updates


def executor_node(
    state: AgentState,
    *,
    registry: AdapterRegistry | None = None,
) -> dict[str, Any]:
    registry = registry or DEFAULT_REGISTRY
    provider = state.get("provider") or ""
    action_name = state.get("action") or ""
    params = state.get("action_params") or {}

    try:
        adapter, action = registry.resolve(provider, action_name)
        action = replace(action, params={**action.params, **params})
        result = adapter.execute(action)
    except Exception as exc:  # noqa: BLE001 — surface as execution failure for Observer
        evidence = _append_evidence(
            state,
            EvidenceItem(
                step="executor",
                provider=provider,
                action=action_name,
                detail={"error": str(exc)},
                ok=False,
            ),
        )
        return {
            "execution_ok": False,
            "execution_result": {"error": str(exc)},
            "evidence": evidence,
        }

    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="executor",
            provider=result.provider,
            action=result.action,
            detail={"data": result.data, "stub": result.stub, "error": result.error},
            ok=result.ok,
        ),
    )
    return {
        "execution_ok": result.ok,
        "execution_result": {
            "ok": result.ok,
            "provider": result.provider,
            "action": result.action,
            "data": result.data,
            "error": result.error,
            "stub": result.stub,
            "evidence": result.evidence,
        },
        "evidence": evidence,
    }


def fallback_node(state: AgentState) -> dict[str, Any]:
    """Degrade / circuit-break path — emit SOP guidance without mutating systems."""
    sop = {
        "title": "Manual SOP fallback",
        "steps": [
            "Acknowledge the alert in the on-call channel",
            "Inspect dashboards / logs for the affected service",
            "Apply the documented runbook; escalate if MTTR budget is exceeded",
        ],
        "reason": state.get("risk_reason") or state.get("block_reason") or "circuit break",
    }
    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="fallback",
            detail=sop,
            ok=True,
        ),
    )
    return {
        "is_fallback": True,
        "execution_ok": True,
        "execution_result": {"sop": sop, "mode": "fallback"},
        "evidence": evidence,
        "observer_notes": "Entered degrade/circuit-break path (is_fallback=True)",
    }


def observer_node(state: AgentState) -> dict[str, Any]:
    """Reflect on execution; schedule retry with error_context when appropriate."""
    ok = bool(state.get("execution_ok"))
    retry_count = int(state.get("retry_count") or 0)
    max_retries = int(state.get("max_retries") or 1)
    result = state.get("execution_result") or {}

    if ok:
        evidence = _append_evidence(
            state,
            EvidenceItem(step="observer", detail={"status": "ok", "retry_count": retry_count}, ok=True),
        )
        return {
            "should_retry": False,
            "observer_notes": "Execution succeeded; proceeding to output.",
            "evidence": evidence,
            "error_context": None,
        }

    error = result.get("error") or "execution failed"
    if retry_count < max_retries and not state.get("blocked"):
        evidence = _append_evidence(
            state,
            EvidenceItem(
                step="observer",
                detail={"status": "retry", "error": error, "retry_count": retry_count + 1},
                ok=False,
            ),
        )
        return {
            "should_retry": True,
            "retry_count": retry_count + 1,
            "error_context": f"previous action failed: {error}; result={result}",
            "observer_notes": f"Retrying with error_context (attempt {retry_count + 1}/{max_retries})",
            "evidence": evidence,
            # clear prior plan so planner re-runs cleanly
            "plan": {},
            "provider": None,
            "action": None,
        }

    evidence = _append_evidence(
        state,
        EvidenceItem(
            step="observer",
            detail={"status": "exhausted", "error": error},
            ok=False,
        ),
    )
    return {
        "should_retry": False,
        "is_fallback": True,
        "observer_notes": "Retries exhausted; degrading to fallback conclusion.",
        "evidence": evidence,
        "error_context": error,
    }


def output_node(state: AgentState) -> dict[str, Any]:
    evidence_items = [
        EvidenceItem(
            step=e.get("step", "?"),
            provider=e.get("provider"),
            action=e.get("action"),
            detail=e.get("detail") or {},
            ok=bool(e.get("ok", True)),
        )
        for e in (state.get("evidence") or [])
    ]

    if state.get("blocked"):
        conclusion = state.get("conclusion") or f"Blocked: {state.get('block_reason')}"
    elif state.get("is_fallback") and not state.get("execution_result", {}).get("sop"):
        conclusion = (
            state.get("observer_notes")
            or "Degraded: unable to complete remediation; follow manual SOP."
        )
    elif state.get("is_fallback"):
        conclusion = (
            "Fallback/circuit-break engaged. Manual SOP issued; no mutating cloud action executed."
        )
    elif state.get("execution_ok"):
        provider = state.get("provider")
        action = state.get("action")
        stub = (state.get("execution_result") or {}).get("stub")
        mode = "stub" if stub else "live"
        conclusion = (
            f"Completed {provider}:{action} ({mode}). "
            f"Risk={state.get('risk_decision')}. See evidence chain."
        )
    else:
        conclusion = "Failed to complete the planned action; see evidence and error_context."

    payload = build_output(
        conclusion,
        evidence_items,
        is_fallback=bool(state.get("is_fallback")),
        hitl_required=bool(state.get("requires_hitl")),
        hitl_approved=state.get("hitl_approved"),
        blocked=bool(state.get("blocked")),
    )
    return {
        "conclusion": payload.conclusion,
        "warnings": payload.warnings,
        "output": payload.to_dict(),
    }


def route_after_input(state: AgentState) -> str:
    if state.get("blocked"):
        return "output"
    return "planner"


def route_after_risk(state: AgentState) -> str:
    decision = state.get("risk_decision")
    if decision == RiskDecision.EXECUTE.value:
        return "executor"
    if decision == RiskDecision.HITL.value:
        return "hitl"
    return "fallback"


def route_after_hitl(state: AgentState) -> str:
    if state.get("hitl_approved"):
        return "executor"
    return "fallback"


def route_after_observer(state: AgentState) -> str:
    if state.get("should_retry"):
        return "input_guard"
    if state.get("is_fallback") and not (state.get("execution_result") or {}).get("sop"):
        # retries exhausted without SOP yet
        return "fallback"
    return "output"
