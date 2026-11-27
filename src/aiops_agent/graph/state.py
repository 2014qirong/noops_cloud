"""LangGraph agent state for the AIOps closed loop."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    # Input
    raw_input: str
    sanitized_input: str
    error_context: str | None

    # Guardrails
    injection_detected: bool
    blocked: bool
    block_reason: str | None
    redactions: int

    # Planner
    plan: dict[str, Any]
    provider: str | None
    action: str | None
    action_params: dict[str, Any]

    # Risk
    risk_decision: str
    risk_reason: str
    risk_level: str
    requires_hitl: bool
    is_fallback: bool

    # HITL
    hitl_approved: bool | None
    hitl_callback: Any  # callable[[dict], bool] | None

    # Execution
    execution_result: dict[str, Any]
    execution_ok: bool

    # Observer
    observer_notes: str
    retry_count: int
    max_retries: int
    should_retry: bool

    # Evidence / output
    evidence: list[dict[str, Any]]
    conclusion: str
    warnings: list[str]
    output: dict[str, Any]

    # Production
    token_used: int
    trace_events: list[dict[str, Any]]

    # Shadow Mode — propose + record; suppress high-risk/write side effects
    shadow_mode: bool
    shadow_proposed: bool
    shadow_suppressed: bool
