"""Shadow Mode harness tests."""

from pathlib import Path

from aiops_agent.graph.graph import run_agent
from aiops_agent.production.shadow import (
    SHADOW_SET,
    ShadowCase,
    compare_shadow,
    get_shadow_case,
    run_shadow,
    run_shadow_case,
    shadow_cases_by_category,
    shadow_enabled,
    write_shadow_report,
)


def test_shadow_set_coverage():
    cats = {c.category for c in SHADOW_SET}
    assert {"read", "write", "guardrail", "provider"} <= cats
    assert len(SHADOW_SET) >= 10
    write_cases = shadow_cases_by_category("write")
    assert all(c.expect_write_suppressed for c in write_cases)


def test_full_shadow_harness_agrees():
    results, metrics = run_shadow()
    disagreed = [r for r in results if not r.agreed]
    assert not disagreed, {
        r.case_id: r.comparison.notes for r in disagreed
    }
    assert metrics.agreement_rate == 1.0
    assert metrics.provider_agreement == 1.0
    assert metrics.action_agreement == 1.0
    assert metrics.write_suppress_rate == 1.0
    assert metrics.read_execute_rate == 1.0


def test_write_suppressed_not_executed():
    case = get_shadow_case("shadow-write-k8s-restart")
    assert case is not None
    result = run_shadow_case(case)
    assert result.agreed, result.comparison.notes
    assert result.comparison.write_suppressed is True
    out = result.agent_output
    assert out["shadow_suppressed"] is True
    assert (out.get("execution_result") or {}).get("mode") == "shadow"
    # No live adapter mutate — evidence has shadow_propose, not a real executor write
    steps = [e.get("step") for e in out.get("evidence") or []]
    assert "shadow_propose" in steps
    assert "hitl" not in steps


def test_read_still_executes_in_shadow():
    case = get_shadow_case("shadow-read-k8s-pods")
    assert case is not None
    result = run_shadow_case(case)
    assert result.agreed, result.comparison.notes
    assert result.comparison.read_executed is True
    out = result.agent_output
    assert out.get("shadow_suppressed") is False
    assert (out.get("execution_result") or {}).get("ok") is True


def test_single_prompt_shadow_mode_flag():
    out = run_agent(
        "Restart the api deployment in default namespace",
        shadow_mode=True,
    )
    assert out["shadow_mode"] is True
    assert out["shadow_suppressed"] is True
    assert out["risk_decision"] == "hitl"
    assert out["action"] == "restart_deployment"
    assert "Shadow mode" in (out.get("conclusion") or "")


def test_write_shadow_report(tmp_path: Path):
    results, metrics = run_shadow(shadow_cases_by_category("read"))
    paths = write_shadow_report(
        results, metrics, output_dir=tmp_path, basename="shadow-sample"
    )
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    text = paths["markdown"].read_text(encoding="utf-8")
    assert "Agreement rate" in text
    assert "Disagreement report" in text


def test_legacy_compare_shadow_and_env_flag():
    cmp = compare_shadow(
        "probe",
        {"provider": "k8s", "action": "get_pods", "risk_decision": "execute"},
        {"provider": "k8s", "action": "get_pods", "risk_decision": "execute"},
    )
    assert cmp.diverged is False
    diverged = compare_shadow(
        "probe",
        {"provider": "k8s", "action": "get_pods"},
        {"provider": "aws", "action": "get_pods"},
    )
    assert diverged.diverged is True
    assert shadow_enabled({"AIOPS_SHADOW_MODE": "1"}) is True
    assert shadow_enabled({"AIOPS_SHADOW_MODE": "0"}) is False


def test_shadow_case_to_dict():
    case = ShadowCase(
        id="demo",
        input="List pods",
        category="read",
        reference_provider="k8s",
        reference_action="get_pods",
    )
    d = case.to_dict()
    assert d["id"] == "demo"
    assert d["reference_provider"] == "k8s"
