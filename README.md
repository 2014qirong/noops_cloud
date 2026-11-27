# noops_cloud

Multi-cloud **AIOps agent** with a LangGraph closed loop:

**Input+Guardrails → Planner → Risk gate → Executor / HITL → Observer → Output+evidence**

Aligned with the project architecture (guardrails, risk branching, degrade/circuit-break, observer retry, production scaffolding).

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │         error_context (retry)       │
                    └─────────────────▲───────────────────┘
                                      │
START → input_guard → planner → risk_gate ─┬─ execute ──┐
            │                              ├─ HITL ─────┤
            │ (blocked)                    └─ fallback ─┤
            │                                           ▼
            └──────────────────────────────→ observer → output → END
```

| Stage | Behavior |
|--------|----------|
| **Input guardrails** | Desensitization (secrets/PII) + prompt-injection detection |
| **Planner** | Provider-agnostic action selection (AWS / Azure / GCP / K8s) |
| **Risk gate** | Read/low → Executor; high-risk write → HITL; reject → `is_fallback` |
| **HITL** | Callback approves/denies mutating actions (default: deny) |
| **Observer** | Reflect; on failure retry with `error_context` back to input |
| **Output** | Conclusion + evidence chain + light hallucination checks |

Core never hardcodes a single cloud: all side effects go through `CloudAdapter`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Read-only demo (stub adapters if credentials missing)
aiops "Show me pods that are crashing in namespace default"

# High-risk write with HITL approve / deny
aiops "Restart the api deployment in default namespace" --hitl approve
aiops "Scale the AWS ASG web-asg capacity" --hitl deny

# Full JSON + catalog
aiops "List AWS CloudWatch alarms" --json
aiops --catalog

# Or module form
python -m aiops_agent "List Azure Monitor alerts"
```

## Multi-cloud adapters

| Provider | Module | Live when | Example actions |
|----------|--------|-----------|-----------------|
| AWS | `adapters/aws.py` | `AWS_ACCESS_KEY_ID` / `AWS_PROFILE` / web identity | `describe_alarms`, `restart_ecs_service` |
| Azure | `adapters/azure.py` | `AZURE_CLIENT_ID` / subscription / tenant | `list_alerts`, `restart_vm` |
| GCP | `adapters/gcp.py` | `GOOGLE_APPLICATION_CREDENTIALS` / project env | `list_incidents`, `resize_mig` |
| K8s | `adapters/k8s.py` | `KUBECONFIG` or `~/.kube/config` | `get_pods`, `restart_deployment` |

Without credentials, adapters return **deterministic stubs** (`stub=True`) so the graph, risk, and HITL paths stay testable offline. Register custom adapters via `AdapterRegistry.register(...)`.

## Evaluation (Golden Set)

Offline harness under `src/aiops_agent/production/eval/`. Uses the **rule-based planner** (deterministic / fake-LLM) and stub adapters — **no cloud credentials or paid API keys** required for CI.

### Run

```bash
# Full harness + JSON/Markdown report under artifacts/
aiops --eval
aiops --eval --report-dir artifacts
aiops --eval --category guardrail   # optional filter

# Pytest (includes full golden-set pass)
pytest -q
pytest -q tests/test_eval.py
```

### Metrics

The report includes:

- **Pass rate** — fraction of golden cases that meet all expectations
- **Provider accuracy** — correct AWS/Azure/GCP/K8s routing when asserted
- **HITL / risk / fallback correctness** — write-path and degrade checks
- **Guardrail TP/FP/TN/FN** — injection blocks vs benign false positives

Artifacts: `artifacts/eval-report.json` and `artifacts/eval-report.md`.

### Add a case

1. Open `src/aiops_agent/production/eval/cases.py`.
2. Append a `GoldenCase(...)` to the matching category list (`_GUARDRAIL_CASES`, `_READ_CASES`, `_HITL_CASES`, `_PROVIDER_CASES`, `_OBSERVER_CASES`).
3. Set only the expectations you care about (`None` = do not assert).
4. For HITL, set `hitl_policy` to `"approve"` or `"deny"`.
5. For Observer retry paths, set `fixture` to `"flaky_k8s"` or `"always_fail_k8s"` (see `eval/fixtures.py`).
6. Run `aiops --eval` / `pytest -q tests/test_eval.py`.

Example:

```python
GoldenCase(
    id="read-aws-alarms-custom",
    input="List AWS CloudWatch alarms that are firing",
    category="read",
    tags=["aws", "read"],
    expect_provider="aws",
    expect_action_contains="describe_alarms",
    expect_risk_decision="execute",
    expect_fallback=False,
)
```

Library usage:

```python
from aiops_agent.production.eval import run_eval, write_report

results, metrics = run_eval()
write_report(results, metrics, output_dir="artifacts")
print(metrics.pass_rate, metrics.provider_accuracy)
```

## Production scaffolding

Under `src/aiops_agent/production/`:

- **Timeouts / model switch** — `TimeoutPolicy`, `maybe_switch_model` (SOP fallback model id)
- **Token budget + cache** — `TokenBudget`, `ResponseCache`
- **Tracing** — `Tracer` protocol, `InMemoryTracer` / `NoOpTracer` (LangSmith-shaped)
- **Golden-set eval** — `production/eval/` harness (`aiops --eval`)
- **Shadow mode** — stub only (`compare_shadow`, `AIOPS_SHADOW_MODE=1`); full pipeline is TODO

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

Coverage focus: graph happy path, injection block, risk gate, HITL approve/deny, observer retry, adapter stubs, golden-set eval harness.

## Library usage

```python
from aiops_agent import run_agent

result = run_agent(
    "List AWS CloudWatch alarms that are firing",
    hitl_callback=lambda payload: False,  # deny writes
)
print(result["conclusion"])
for step in result["evidence"]:
    print(step)
```

## Layout

```
src/aiops_agent/
  adapters/          # AWS, Azure, GCP, K8s + registry
  guardrails/        # input desensitization / injection; output evidence
  risk/              # risk gate + whitelist / blocklist
  graph/             # LangGraph state, nodes, planner, compile
  production/
    eval/            # golden set, runner, metrics, report, fixtures
    shadow.py        # shadow mode stub (TODO)
    ...
  cli.py
tests/
```
