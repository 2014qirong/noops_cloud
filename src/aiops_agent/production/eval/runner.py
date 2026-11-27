"""Golden-set evaluation runner.

Executes cases against ``run_agent`` with deterministic HITL policies and
optional fixture registries — CI needs no cloud credentials or paid LLM APIs
(the planner is rule-based / fake-LLM).
"""

from __future__ import annotations

from typing import Any, Callable

from aiops_agent.adapters.registry import AdapterRegistry, DEFAULT_REGISTRY
from aiops_agent.production.eval.cases import GOLDEN_SET, GoldenCase
from aiops_agent.production.eval.fixtures import build_fixture_registry
from aiops_agent.production.eval.metrics import CaseResult, EvalMetrics, compute_metrics

# NOTE: run_agent is imported lazily inside run_case to avoid
# production → eval → graph → production circular imports.


HitlCallback = Callable[[dict[str, Any]], bool]


def _hitl_callback(policy: str) -> HitlCallback | None:
    if policy == "approve":
        return lambda _payload: True
    if policy == "deny":
        return lambda _payload: False
    return None  # none → default deny inside hitl_node


def _check(case: GoldenCase, out: dict[str, Any]) -> CaseResult:
    checks: dict[str, Any] = {}
    failures: list[str] = []

    def fail(key: str, msg: str) -> None:
        checks[key] = False
        failures.append(msg)

    def ok(key: str, value: Any = True) -> None:
        checks[key] = value if value is not True else True

    if case.expect_blocked is not None:
        actual = bool(out.get("blocked"))
        checks["blocked"] = actual
        if actual == case.expect_blocked:
            ok("blocked_ok")
        else:
            fail("blocked_ok", f"blocked expected={case.expect_blocked} got={actual}")

    if case.expect_hitl is not None:
        hitl = bool(out.get("hitl_required")) or out.get("risk_decision") == "hitl"
        # After deny, risk_decision becomes fallback but hitl_required stays True
        # and evidence should contain a hitl step.
        if not hitl and case.expect_hitl:
            steps = [e.get("step") for e in (out.get("evidence") or [])]
            hitl = "hitl" in steps
        checks["hitl"] = hitl
        if hitl == case.expect_hitl:
            ok("hitl_ok")
        else:
            fail("hitl_ok", f"hitl expected={case.expect_hitl} got={hitl}")

    if case.expect_fallback is not None:
        fb = bool(out.get("is_fallback"))
        checks["fallback"] = fb
        if fb == case.expect_fallback:
            ok("fallback_ok")
        else:
            fail("fallback_ok", f"fallback expected={case.expect_fallback} got={fb}")

    if case.expect_provider is not None:
        provider = out.get("provider") or (out.get("plan") or {}).get("provider")
        # After exhausted retry → fallback, provider may still be set on state.
        checks["provider"] = provider
        if provider == case.expect_provider:
            ok("provider_ok")
        else:
            fail(
                "provider_ok",
                f"provider expected={case.expect_provider!r} got={provider!r}",
            )

    if case.expect_action_contains is not None:
        action = out.get("action") or (out.get("plan") or {}).get("action")
        # HITL deny → fallback clears nothing but action should remain from plan
        if action is None:
            for e in reversed(out.get("evidence") or []):
                if e.get("step") in {"planner", "risk_gate", "hitl", "executor"} and e.get("action"):
                    action = e.get("action")
                    break
        checks["action"] = action
        matched = bool(action) and case.expect_action_contains in str(action)
        if matched:
            ok("action_ok")
        else:
            fail(
                "action_ok",
                f"action containing {case.expect_action_contains!r} got={action!r}",
            )

    if case.expect_risk_decision is not None:
        decision = out.get("risk_decision")
        checks["risk_decision"] = decision
        if decision == case.expect_risk_decision:
            ok("risk_ok")
        else:
            fail(
                "risk_ok",
                f"risk_decision expected={case.expect_risk_decision!r} got={decision!r}",
            )

    if case.expect_hitl_approved is not None:
        approved = out.get("hitl_approved")
        checks["hitl_approved"] = approved
        if approved == case.expect_hitl_approved:
            ok("hitl_approved_ok")
        else:
            fail(
                "hitl_approved_ok",
                f"hitl_approved expected={case.expect_hitl_approved} got={approved}",
            )

    if case.expect_retry is not None:
        retries = int(out.get("retry_count") or 0)
        checks["retry_count"] = retries
        did_retry = retries >= 1
        if did_retry == case.expect_retry:
            ok("retry_ok")
        else:
            fail("retry_ok", f"retry expected={case.expect_retry} retry_count={retries}")

    if case.expect_execution_ok is not None:
        result = out.get("execution_result") or {}
        exec_ok = result.get("ok")
        # SOP fallback payload has mode=fallback without an explicit ok flag
        if exec_ok is None and result.get("mode") == "fallback":
            exec_ok = True
        if exec_ok is None:
            exec_ok = False
        checks["execution_ok"] = exec_ok
        if bool(exec_ok) == case.expect_execution_ok:
            ok("execution_ok_check")
        else:
            fail(
                "execution_ok_check",
                f"execution_ok expected={case.expect_execution_ok} got={exec_ok}",
            )

    if case.expect_min_redactions is not None:
        redactions = int(out.get("redactions") or 0)
        checks["redactions"] = redactions
        if redactions >= case.expect_min_redactions:
            ok("redactions_ok")
        else:
            fail(
                "redactions_ok",
                f"redactions expected>={case.expect_min_redactions} got={redactions}",
            )

    return CaseResult(
        case_id=case.id,
        category=case.category,
        passed=not failures,
        checks=checks,
        failures=failures,
        output=out,
        tags=list(case.tags),
    )


def run_case(case: GoldenCase, *, max_retries: int = 1) -> CaseResult:
    """Execute a single golden case against the agent."""
    from aiops_agent.graph.graph import run_agent

    registry: AdapterRegistry
    if case.fixture:
        registry = build_fixture_registry(case.fixture)
    else:
        registry = DEFAULT_REGISTRY

    out = run_agent(
        case.input,
        registry=registry,
        hitl_callback=_hitl_callback(case.hitl_policy),
        max_retries=max_retries,
    )
    return _check(case, out)


def run_golden_set(
    runner: Callable[[str], dict[str, Any]] | None = None,
    cases: list[GoldenCase] | None = None,
) -> list[Any]:
    """Backward-compatible API used by CLI / older tests.

    When ``runner`` is provided, use the legacy check style (EvalResult-like).
    When omitted, use the full harness and return ``CaseResult`` list.
    """
    selected = cases or GOLDEN_SET
    if runner is None:
        return [run_case(case) for case in selected]

    # Legacy path: caller supplies a text→dict callable (e.g. CLI deny-all).
    from aiops_agent.production.eval_stub import EvalResult

    results: list[EvalResult] = []
    for case in selected:
        out = runner(case.input)
        # Map through checker but adapt hitl_policy from case when possible
        cr = _check(case, out)
        results.append(
            EvalResult(
                case_id=cr.case_id,
                passed=cr.passed,
                details={**cr.checks, "failures": cr.failures},
            )
        )
    return results


def run_eval(
    cases: list[GoldenCase] | None = None,
    *,
    max_retries: int = 1,
) -> tuple[list[CaseResult], EvalMetrics]:
    """Run the full eval harness and return (results, metrics)."""
    selected = cases or GOLDEN_SET
    results = [run_case(case, max_retries=max_retries) for case in selected]
    metrics = compute_metrics(results, selected)
    return results, metrics
