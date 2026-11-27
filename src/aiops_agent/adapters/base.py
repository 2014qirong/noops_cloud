"""Provider-agnostic cloud / platform adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ActionRisk(str, Enum):
    READ = "read"
    LOW = "low"
    HIGH = "high"
    REJECT = "reject"


@dataclass(frozen=True)
class CloudAction:
    """A normalized action the planner can request of any provider."""

    name: str
    risk: ActionRisk
    description: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    mutating: bool = False


@dataclass
class ActionResult:
    ok: bool
    provider: str
    action: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    stub: bool = False
    evidence: dict[str, Any] = field(default_factory=dict)


class CloudAdapter(ABC):
    """Interface every cloud / platform adapter must implement."""

    provider: str

    @abstractmethod
    def available(self) -> bool:
        """True when credentials / cluster context are present."""

    @abstractmethod
    def list_actions(self) -> list[CloudAction]:
        """Actions this adapter can execute."""

    @abstractmethod
    def execute(self, action: CloudAction) -> ActionResult:
        """Run *action*; stub safely when credentials are missing."""

    def get_action(self, name: str) -> CloudAction | None:
        for action in self.list_actions():
            if action.name == name:
                return action
        return None
