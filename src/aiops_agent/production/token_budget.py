"""Token budget + simple in-memory cache scaffolding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TokenBudget:
    max_tokens: int = 8_000
    used: int = 0

    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used)

    def consume(self, n: int) -> bool:
        """Reserve *n* tokens. Returns False if over budget."""
        if self.used + n > self.max_tokens:
            return False
        self.used += n
        return True

    def estimate(self, text: str) -> int:
        # Rough heuristic: ~4 chars per token.
        return max(1, len(text) // 4)


@dataclass
class ResponseCache:
    """Tiny TTL-less cache for identical sanitized prompts (scaffold)."""

    store: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str) -> Any | None:
        return self.store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.store[key] = value
