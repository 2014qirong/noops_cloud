from aiops_agent.adapters.base import ActionRisk, CloudAction
from aiops_agent.risk.gate import RiskDecision, assess_risk


def test_read_action_executes():
    action = CloudAction(name="get_pods", risk=ActionRisk.READ)
    verdict = assess_risk(action)
    assert verdict.decision == RiskDecision.EXECUTE
    assert not verdict.requires_hitl


def test_high_risk_write_requires_hitl():
    action = CloudAction(name="restart_deployment", risk=ActionRisk.HIGH, mutating=True)
    verdict = assess_risk(action)
    assert verdict.decision == RiskDecision.HITL
    assert verdict.requires_hitl


def test_blocklist_rejects():
    action = CloudAction(name="delete_cluster", risk=ActionRisk.LOW)
    verdict = assess_risk(action)
    assert verdict.decision == RiskDecision.REJECT
    assert verdict.is_fallback


def test_missing_action_fallback():
    verdict = assess_risk(None)
    assert verdict.decision == RiskDecision.FALLBACK
    assert verdict.is_fallback
