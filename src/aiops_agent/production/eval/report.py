"""Write short JSON + Markdown report artifacts for an eval run."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiops_agent.production.eval.metrics import CaseResult, EvalMetrics


def build_report_payload(
    results: list[CaseResult],
    metrics: EvalMetrics,
    *,
    title: str = "AIOps Golden Set Eval",
) -> dict[str, Any]:
    failed = [r.to_dict() for r in results if not r.passed]
    return {
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics.to_dict(),
        "results": [r.to_dict() for r in results],
        "failed_cases": failed,
        "notes": [
            "Runner uses the rule-based planner (deterministic / fake-LLM).",
            "Adapters return stubs without cloud credentials.",
            "Shadow Mode is a separate harness (`aiops --shadow`); golden eval is unchanged.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    m = payload["metrics"]
    lines = [
        f"# {payload['title']}",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- **Pass rate:** {m['passed']}/{m['total']} ({m['pass_rate']:.1%})",
        f"- **Provider accuracy:** {_fmt(m.get('provider_accuracy'))}",
        f"- **HITL correctness:** {_fmt(m.get('hitl_correctness'))}",
        f"- **Risk correctness:** {_fmt(m.get('risk_correctness'))}",
        f"- **Fallback correctness:** {_fmt(m.get('fallback_correctness'))}",
        "",
        "### Guardrails",
        "",
        f"- TP={m['guardrail']['true_positives']} FN={m['guardrail']['false_negatives']} "
        f"TN={m['guardrail']['true_negatives']} FP={m['guardrail']['false_positives']}",
        f"- Precision={_fmt(m['guardrail'].get('precision'))} "
        f"Recall={_fmt(m['guardrail'].get('recall'))}",
        "",
        "### By category",
        "",
        "| Category | Passed | Total | Rate |",
        "|----------|--------|-------|------|",
    ]
    for cat, stats in (m.get("by_category") or {}).items():
        rate = stats.get("pass_rate")
        rate_s = f"{rate:.1%}" if isinstance(rate, float) else "n/a"
        lines.append(f"| {cat} | {stats['passed']} | {stats['total']} | {rate_s} |")

    failed = payload.get("failed_cases") or []
    lines.extend(["", "## Failed cases", ""])
    if not failed:
        lines.append("_None — all cases passed._")
    else:
        for item in failed:
            lines.append(f"- `{item['case_id']}`: {', '.join(item.get('failures') or [])}")

    lines.extend(["", "## Notes", ""])
    for note in payload.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def write_report(
    results: list[CaseResult],
    metrics: EvalMetrics,
    *,
    output_dir: str | Path,
    basename: str = "eval-report",
) -> dict[str, Path]:
    """Write ``{basename}.json`` and ``{basename}.md`` under *output_dir*."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = build_report_payload(results, metrics)
    json_path = out / f"{basename}.json"
    md_path = out / f"{basename}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
