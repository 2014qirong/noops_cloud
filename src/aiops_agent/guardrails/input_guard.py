"""Input guardrails: desensitization + injection detection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Patterns that look like secrets / PII (redacted in place).
_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[AWS_ACCESS_KEY_REDACTED]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer [REDACTED]"),
    (
        re.compile(
            r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"
        ),
        "[EMAIL_REDACTED]",
    ),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP_REDACTED]"),
]

# Classic prompt-injection / jailbreak signals.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|rules)"),
    re.compile(r"(?i)disregard\s+(your|the)\s+(system|safety)\s+(prompt|rules)"),
    re.compile(r"(?i)you\s+are\s+now\s+(dan|unrestricted|jailbroken)"),
    re.compile(r"(?i)<\s*/?\s*system\s*>"),
    re.compile(r"(?i)reveal\s+(your|the)\s+(system\s+)?prompt"),
    re.compile(r"(?i)do\s+not\s+follow\s+(safety|policy|guardrail)"),
]


@dataclass
class InputGuardResult:
    original: str
    sanitized: str
    injection_detected: bool = False
    injection_matches: list[str] = field(default_factory=list)
    redactions: int = 0
    blocked: bool = False
    reason: str | None = None


def desensitize(text: str) -> tuple[str, int]:
    """Mask secrets / PII. Returns (sanitized_text, redaction_count)."""
    out = text
    count = 0
    for pattern, repl in _SECRET_PATTERNS:
        out, n = pattern.subn(repl, out)
        count += n
    return out, count


def detect_injection(text: str) -> list[str]:
    """Return matched injection pattern snippets."""
    hits: list[str] = []
    for pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            hits.append(m.group(0))
    return hits


def apply_input_guardrails(text: str, *, block_on_injection: bool = True) -> InputGuardResult:
    sanitized, redactions = desensitize(text)
    matches = detect_injection(sanitized)
    blocked = bool(matches) and block_on_injection
    return InputGuardResult(
        original=text,
        sanitized=sanitized,
        injection_detected=bool(matches),
        injection_matches=matches,
        redactions=redactions,
        blocked=blocked,
        reason="prompt injection detected" if blocked else None,
    )
