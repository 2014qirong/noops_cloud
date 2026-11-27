"""Shadow mode stub — compare candidate plan vs production without side effects.

TODO: Expand into a full shadow pipeline (async candidate graph, traffic
mirroring, divergence alerts). Out of scope for the golden-set eval PR —
keep this module as a minimal stub only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShadowComparison:
    prompt: str
    production: dict[str, Any]
    candidate: dict[str, Any]
    diverged: bool
    notes: list[str] = field(default_factory=list)


def compare_shadow(
    prompt: str,
    production: dict[str, Any],
    candidate: dict[str, Any],
) -> ShadowComparison:
    """Diff key decision fields between production and candidate outputs."""
    keys = ("provider", "action", "risk_decision", "is_fallback", "blocked")
    notes: list[str] = []
    diverged = False
    for key in keys:
        pv = production.get(key)
        cv = candidate.get(key)
        if pv != cv:
            diverged = True
            notes.append(f"{key}: prod={pv!r} candidate={cv!r}")
    return ShadowComparison(
        prompt=prompt,
        production=production,
        candidate=candidate,
        diverged=diverged,
        notes=notes,
    )


def shadow_enabled(env: dict[str, str] | None = None) -> bool:
    import os

    source = env if env is not None else os.environ
    return source.get("AIOPS_SHADOW_MODE", "").lower() in {"1", "true", "yes"}
