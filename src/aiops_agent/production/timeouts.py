"""Timeout + model-switch scaffolding for production hardening."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TimeoutPolicy:
    """Per-stage soft timeouts (seconds). Scaffold — not a hard kill switch."""

    input_guard: float = 2.0
    planner: float = 30.0
    executor: float = 60.0
    observer: float = 15.0
    total: float = 120.0
    # When primary model times out, switch to this fallback model id.
    fallback_model: str = "sop-fallback"


@dataclass
class ModelSwitchResult:
    switched: bool
    from_model: str
    to_model: str
    reason: str


def maybe_switch_model(
    *,
    primary: str,
    elapsed: float,
    budget: float,
    policy: TimeoutPolicy | None = None,
) -> ModelSwitchResult:
    policy = policy or TimeoutPolicy()
    if elapsed >= budget:
        return ModelSwitchResult(
            switched=True,
            from_model=primary,
            to_model=policy.fallback_model,
            reason=f"elapsed {elapsed:.1f}s >= budget {budget:.1f}s",
        )
    return ModelSwitchResult(
        switched=False,
        from_model=primary,
        to_model=primary,
        reason="within budget",
    )
