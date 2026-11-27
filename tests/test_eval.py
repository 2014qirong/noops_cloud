"""Golden-set evaluation harness tests."""

from pathlib import Path

from aiops_agent.production.eval import (
    GOLDEN_SET,
    GoldenCase,
    get_case,
    run_case,
    run_eval,
    write_report,
)
from aiops_agent.production.eval.cases import cases_by_category
from aiops_agent.production.eval_stub import run_golden_set as legacy_run_golden_set
from aiops_agent.graph.graph import run_agent


def test_golden_set_has_required_coverage():
    cats = {c.category for c in GOLDEN_SET}
    assert {"guardrail", "read", "write_hitl", "provider", "observer"} <= cats
    providers = set()
    for c in GOLDEN_SET:
        if c.expect_provider:
            providers.add(c.expect_provider)
    assert {"aws", "azure", "gcp", "k8s"} <= providers
    assert len(GOLDEN_SET) >= 20


def test_full_eval_harness_passes():
    results, metrics = run_eval()
    failed = [r for r in results if not r.passed]
    assert not failed, {r.case_id: r.failures for r in failed}
    assert metrics.pass_rate == 1.0
    assert metrics.provider_accuracy == 1.0
    assert metrics.hitl_correctness == 1.0
    assert metrics.guardrail_false_positives == 0
    assert metrics.guardrail_true_positives >= 1


def test_write_report_artifact(tmp_path: Path):
    results, metrics = run_eval(cases_by_category("read"))
    paths = write_report(results, metrics, output_dir=tmp_path, basename="sample")
    assert paths["json"].exists()
    assert paths["markdown"].exists()
    text = paths["markdown"].read_text(encoding="utf-8")
    assert "Pass rate" in text
    assert "By category" in text


def test_run_case_hitl_approve():
    case = get_case("hitl-k8s-restart-approve")
    assert case is not None
    result = run_case(case)
    assert result.passed, result.failures
    assert result.output["hitl_approved"] is True


def test_observer_fixture_retry():
    case = get_case("observer-retry-then-success")
    assert case is not None
    result = run_case(case)
    assert result.passed, result.failures
    assert result.output["retry_count"] >= 1


def test_legacy_run_golden_set_with_runner_still_works():
    # Legacy API: custom runner ignores per-case hitl_policy — filter to deny-safe cases.
    cases = [
        c
        for c in GOLDEN_SET
        if c.hitl_policy != "approve" and c.fixture is None
    ]
    results = legacy_run_golden_set(
        lambda text: run_agent(text, hitl_callback=lambda _p: False),
        cases=cases,
    )
    failed = [r for r in results if not r.passed]
    assert not failed, {r.case_id: r.details for r in failed}


def test_category_filter():
    guard = cases_by_category("guardrail")
    assert all(c.category == "guardrail" for c in guard)
    assert len(guard) >= 3
