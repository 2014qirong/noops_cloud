"""Assemble the LangGraph closed loop.

Flow: Input+Guardrails → Planner → Risk gate → Executor|HITL|Fallback → Observer → Output
Observer may retry back to Input with error_context.
"""

from __future__ import annotations

from functools import partial
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from aiops_agent.adapters.registry import AdapterRegistry, DEFAULT_REGISTRY
from aiops_agent.graph.nodes import (
    executor_node,
    fallback_node,
    hitl_node,
    input_guard_node,
    observer_node,
    output_node,
    planner_node,
    risk_gate_node,
    route_after_hitl,
    route_after_input,
    route_after_observer,
    route_after_risk,
    shadow_propose_node,
)
from aiops_agent.graph.state import AgentState
from aiops_agent.production.token_budget import TokenBudget
from aiops_agent.production.tracing import InMemoryTracer, NoOpTracer, Tracer


def build_graph(
    *,
    registry: AdapterRegistry | None = None,
    checkpointer: Any = None,
):
    """Compile the AIOps LangGraph. Optional checkpointer enables HITL persistence."""
    registry = registry or DEFAULT_REGISTRY

    graph = StateGraph(AgentState)

    graph.add_node("input_guard", input_guard_node)
    graph.add_node("planner", partial(planner_node, registry=registry))
    graph.add_node("risk_gate", partial(risk_gate_node, registry=registry))
    graph.add_node("hitl", hitl_node)
    graph.add_node("shadow_propose", shadow_propose_node)
    graph.add_node("executor", partial(executor_node, registry=registry))
    graph.add_node("fallback", fallback_node)
    graph.add_node("observer", observer_node)
    graph.add_node("output", output_node)

    graph.add_edge(START, "input_guard")
    graph.add_conditional_edges(
        "input_guard",
        route_after_input,
        {"planner": "planner", "output": "output"},
    )
    graph.add_edge("planner", "risk_gate")
    graph.add_conditional_edges(
        "risk_gate",
        route_after_risk,
        {
            "executor": "executor",
            "hitl": "hitl",
            "shadow_propose": "shadow_propose",
            "fallback": "fallback",
        },
    )
    graph.add_conditional_edges(
        "hitl",
        route_after_hitl,
        {"executor": "executor", "fallback": "fallback"},
    )
    graph.add_edge("shadow_propose", "observer")
    graph.add_edge("executor", "observer")
    graph.add_edge("fallback", "observer")
    graph.add_conditional_edges(
        "observer",
        route_after_observer,
        {"input_guard": "input_guard", "fallback": "fallback", "output": "output"},
    )
    graph.add_edge("output", END)

    return graph.compile(checkpointer=checkpointer)


def run_agent(
    user_input: str,
    *,
    registry: AdapterRegistry | None = None,
    hitl_callback: Callable[[dict[str, Any]], bool] | None = None,
    max_retries: int = 1,
    tracer: Tracer | None = None,
    token_budget: TokenBudget | None = None,
    shadow_mode: bool = False,
) -> dict[str, Any]:
    """Run one closed-loop turn and return a flat result dict for CLI / evals.

    When ``shadow_mode`` is True, high-risk/write actions are proposed and
    recorded but never executed; safe read/low-risk actions may still run.
    """
    registry = registry or DEFAULT_REGISTRY
    tracer = tracer or NoOpTracer()
    budget = token_budget or TokenBudget()

    span = tracer.start_span("aiops.run", input_preview=user_input[:120])
    estimated = budget.estimate(user_input)
    if not budget.consume(estimated):
        tracer.end_span(span, status="token_budget_exceeded")
        return {
            "blocked": True,
            "is_fallback": True,
            "conclusion": "Token budget exceeded before planning",
            "evidence": [],
            "token_used": budget.used,
        }

    app = build_graph(registry=registry)
    initial: AgentState = {
        "raw_input": user_input,
        "retry_count": 0,
        "max_retries": max_retries,
        "evidence": [],
        "hitl_callback": hitl_callback,
        "is_fallback": False,
        "blocked": False,
        "should_retry": False,
        "shadow_mode": shadow_mode,
        "shadow_proposed": False,
        "shadow_suppressed": False,
    }
    final: AgentState = app.invoke(initial)
    tracer.event(
        "aiops.completed",
        risk=final.get("risk_decision"),
        fallback=final.get("is_fallback"),
        shadow=shadow_mode,
    )
    tracer.end_span(span, status="ok")

    output = final.get("output") or {}
    return {
        "conclusion": final.get("conclusion") or output.get("conclusion"),
        "evidence": final.get("evidence") or output.get("evidence") or [],
        "warnings": final.get("warnings") or [],
        "provider": final.get("provider"),
        "action": final.get("action"),
        "action_params": final.get("action_params") or (final.get("plan") or {}).get("params") or {},
        "plan": final.get("plan"),
        "risk_decision": final.get("risk_decision"),
        "risk_reason": final.get("risk_reason"),
        "is_fallback": bool(final.get("is_fallback")),
        "hitl_required": bool(final.get("requires_hitl")),
        "hitl_approved": final.get("hitl_approved"),
        "blocked": bool(final.get("blocked")),
        "execution_result": final.get("execution_result"),
        "observer_notes": final.get("observer_notes"),
        "retry_count": final.get("retry_count") or 0,
        "redactions": final.get("redactions") or 0,
        "token_used": budget.used,
        "shadow_mode": bool(final.get("shadow_mode") or shadow_mode),
        "shadow_proposed": bool(final.get("shadow_proposed")),
        "shadow_suppressed": bool(final.get("shadow_suppressed")),
        "output": output,
        "adapter_status": registry.status(),
    }


def run_agent_with_tracing(user_input: str, **kwargs: Any) -> tuple[dict[str, Any], InMemoryTracer]:
    tracer = InMemoryTracer()
    result = run_agent(user_input, tracer=tracer, **kwargs)
    return result, tracer
