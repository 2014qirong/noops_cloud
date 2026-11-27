"""Persist Shadow Mode comparison artifacts (JSON + Markdown)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiops_agent.production.shadow.metrics import ShadowCaseResult, ShadowMetrics


def build_shadow_report_payload(
    results: list[ShadowCaseResult],
    metrics: ShadowMetrics,
    *,
    title: str = "AIOps Shadow Mode Report",
) -> dict[str, Any]:
    disagreements = [r.to_dict() for r in results if not r.agreed]
    return {
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics.to_dict(),
        "results": [r.to_dict() for r in results],
        "disagreements": disagreements,
        "notes": [
            "Shadow Mode proposes actions but does not execute high-risk/write side effects.",
            "Safe read/low-risk actions may still run (stub adapters offline).",
            "Agreement compares agent proposals to human/operator reference SOP cases.",
            "Runner uses the rule-based planner (deterministic / fake-LLM); no cloud/LLM keys.",
        ],
    }


def render_shadow_markdown(payload: dict[str, Any]) -> str:
    m = payload["metrics"]
    lines = [
        f"# {payload['title']}",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- **Agreement rate:** {m['agreed']}/{m['total']} ({m['agreement_rate']:.1%})",
        f"- **Provider agreement:** {_fmt(m.get('provider_agreement'))}",
        f"- **Action agreement:** {_fmt(m.get('action_agreement'))}",
        f"- **Risk agreement:** {_fmt(m.get('risk_agreement'))}",
        f"- **Write suppress rate:** {_fmt(m.get('write_suppress_rate'))}",
        f"- **Read execute rate:** {_fmt(m.get('read_execute_rate'))}",
        f"- **Field disagreements:** {m.get('disagreement_count', 0)}",
        "",
        "### By category",
        "",
        "| Category | Agreed | Total | Rate |",
        "|----------|--------|-------|------|",
    ]
    for cat, stats in (m.get("by_category") or {}).items():
        rate = stats.get("agreement_rate")
        rate_s = f"{rate:.1%}" if isinstance(rate, float) else "n/a"
        lines.append(f"| {cat} | {stats['agreed']} | {stats['total']} | {rate_s} |")

    disagreements = payload.get("disagreements") or []
    lines.extend(["", "## Disagreement report", ""])
    if not disagreements:
        lines.append("_None — all proposals agreed with human reference._")
    else:
        for item in disagreements:
            notes = item.get("comparison", {}).get("notes") or []
            detail = "; ".join(notes) if notes else "see diffs"
            lines.append(f"- `{item['case_id']}`: {detail}")

    lines.extend(["", "## Notes", ""])
    for note in payload.get("notes") or []:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def write_shadow_report(
    results: list[ShadowCaseResult],
    metrics: ShadowMetrics,
    *,
    output_dir: str | Path,
    basename: str = "shadow-report",
) -> dict[str, Path]:
    """Write ``{basename}.json`` and ``{basename}.md`` under *output_dir*."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = build_shadow_report_payload(results, metrics)
    json_path = out / f"{basename}.json"
    md_path = out / f"{basename}.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(render_shadow_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
