"""CLI entrypoint: `aiops "show crashing pods"` or `python -m aiops_agent.cli`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aiops_agent.adapters.registry import DEFAULT_REGISTRY
from aiops_agent.graph.graph import run_agent
from aiops_agent.production.eval import GOLDEN_SET, run_eval, write_report


def _approve_all(payload: dict) -> bool:
    print(f"[HITL] auto-approve (demo): {payload.get('provider')}:{payload.get('action')}", file=sys.stderr)
    return True


def _deny_all(payload: dict) -> bool:
    print(f"[HITL] deny: {payload.get('provider')}:{payload.get('action')}", file=sys.stderr)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Multi-cloud AIOps agent")
    parser.add_argument("prompt", nargs="?", help="Natural-language ops request")
    parser.add_argument(
        "--hitl",
        choices=("approve", "deny", "none"),
        default="none",
        help="HITL policy for high-risk writes (default: none → deny)",
    )
    parser.add_argument("--catalog", action="store_true", help="Print adapter action catalog")
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Run golden-set evaluation harness (deterministic; no cloud/LLM keys)",
    )
    parser.add_argument(
        "--report-dir",
        default="artifacts",
        help="Directory for eval report JSON/Markdown (default: artifacts/)",
    )
    parser.add_argument(
        "--category",
        default=None,
        help="Optional golden-set category filter (guardrail|read|write_hitl|provider|observer)",
    )
    parser.add_argument("--json", action="store_true", help="Emit full JSON result")
    args = parser.parse_args(argv)

    if args.catalog:
        print(json.dumps(DEFAULT_REGISTRY.catalog(), indent=2))
        return 0

    if args.eval:
        cases = GOLDEN_SET
        if args.category:
            cases = [c for c in GOLDEN_SET if c.category == args.category]
            if not cases:
                print(f"No cases for category={args.category!r}", file=sys.stderr)
                return 2
        results, metrics = run_eval(cases)
        paths = write_report(results, metrics, output_dir=Path(args.report_dir))
        payload = {
            "metrics": metrics.to_dict(),
            "results": [
                {"id": r.case_id, "passed": r.passed, "failures": r.failures, "checks": r.checks}
                for r in results
            ],
            "report": {k: str(v) for k, v in paths.items()},
        }
        print(json.dumps(payload, indent=2, default=str))
        print(
            f"\nEval: {metrics.passed}/{metrics.total} passed "
            f"(rate={metrics.pass_rate:.1%}); "
            f"reports → {paths['json']}, {paths['markdown']}",
            file=sys.stderr,
        )
        return 0 if metrics.failed == 0 else 1

    if not args.prompt:
        parser.error("prompt is required unless --catalog / --eval")

    hitl_cb = None
    if args.hitl == "approve":
        hitl_cb = _approve_all
    elif args.hitl == "deny":
        hitl_cb = _deny_all

    result = run_agent(args.prompt, hitl_callback=hitl_cb)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result.get("conclusion"))
        print("--- evidence ---")
        for item in result.get("evidence") or []:
            print(f"  [{item.get('step')}] ok={item.get('ok')} {item.get('provider') or ''} {item.get('action') or ''}")
        if result.get("is_fallback"):
            print("(is_fallback=True)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
