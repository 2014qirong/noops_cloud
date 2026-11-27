"""Risk gate: read/low → execute; high-risk write → HITL; reject → fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from aiops_agent.adapters.base import ActionRisk, CloudAction


class RiskDecision(str, Enum):
    EXECUTE = "execute"
    HITL = "hitl"
    FALLBACK = "fallback"
    REJECT = "reject"


# Commands that are never auto-executed even if marked low risk elsewhere.
_BLOCKLIST = frozenset(
    {
        "delete_namespace",
        "delete_cluster",
        "rm_rf",
        "drop_database",
        "disable_monitoring",
    }
)

# Explicit whitelist of auto-executable read/low actions (by action name).
_READ_WHITELIST = frozenset(
    {
        "describe_alarms",
        "get_metric_stats",
        "list_alerts",
        "get_metrics",
        "list_incidents",
        "query_timeseries",
        "get_pods",
        "get_events",
        "describe_deployment",
    }
)


@dataclass
class RiskVerdict:
    decision: RiskDecision
    reason: str
    risk: ActionRisk
    requires_hitl: bool = False
    is_fallback: bool = False


def assess_risk(action: CloudAction | None, *, force_reject: bool = False) -> RiskVerdict:
    """Classify a planned action into execute / hitl / fallback / reject."""
    if action is None or force_reject:
        return RiskVerdict(
            decision=RiskDecision.FALLBACK,
            reason="no actionable plan or forced reject",
            risk=ActionRisk.REJECT,
            is_fallback=True,
        )

    if action.name in _BLOCKLIST or action.risk == ActionRisk.REJECT:
        return RiskVerdict(
            decision=RiskDecision.REJECT,
            reason=f"action {action.name!r} is blocked",
            risk=ActionRisk.REJECT,
            is_fallback=True,
        )

    if action.mutating or action.risk == ActionRisk.HIGH:
        return RiskVerdict(
            decision=RiskDecision.HITL,
            reason=f"high-risk write {action.name!r} requires human approval",
            risk=ActionRisk.HIGH,
            requires_hitl=True,
        )

    if action.risk in (ActionRisk.READ, ActionRisk.LOW) or action.name in _READ_WHITELIST:
        return RiskVerdict(
            decision=RiskDecision.EXECUTE,
            reason=f"read/low-risk action {action.name!r} may auto-execute",
            risk=action.risk if action.risk != ActionRisk.REJECT else ActionRisk.READ,
        )

    # Unknown / unlisted → treat as HITL for safety
    return RiskVerdict(
        decision=RiskDecision.HITL,
        reason=f"unlisted action {action.name!r} requires human approval",
        risk=ActionRisk.HIGH,
        requires_hitl=True,
    )
