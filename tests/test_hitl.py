from aiops_agent.graph.graph import run_agent


def test_high_risk_write_denied_without_hitl():
    result = run_agent("Restart the api deployment in production namespace")
    assert result["hitl_required"] or result["risk_decision"] in {"hitl", "fallback"}
    assert result["is_fallback"] is True
    assert result["hitl_approved"] in (False, None)
    # no mutating success without approval
    steps = [e["step"] for e in result["evidence"]]
    assert "hitl" in steps or "fallback" in steps


def test_high_risk_write_approved_via_callback():
    result = run_agent(
        "Restart the api deployment in default namespace",
        hitl_callback=lambda _payload: True,
    )
    assert result["hitl_approved"] is True
    assert result["execution_result"]["ok"] is True
    assert result["execution_result"]["action"] == "restart_deployment"
    assert result["is_fallback"] is False


def test_scale_requires_hitl_on_aws():
    result = run_agent(
        "Scale the AWS ASG web-asg capacity",
        hitl_callback=lambda _p: False,
    )
    assert result["provider"] == "aws"
    assert result["is_fallback"] is True
