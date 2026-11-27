"""Tracing interface (LangSmith-compatible shape; no-op by default)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4


class Tracer(Protocol):
    def start_span(self, name: str, **attrs: Any) -> str: ...
    def end_span(self, span_id: str, **attrs: Any) -> None: ...
    def event(self, name: str, **attrs: Any) -> None: ...


@dataclass
class SpanRecord:
    id: str
    name: str
    attrs: dict[str, Any] = field(default_factory=dict)
    ended: bool = False
    end_attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class InMemoryTracer:
    """Local tracer for tests / shadow runs. Swap for LangSmith later."""

    spans: list[SpanRecord] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def start_span(self, name: str, **attrs: Any) -> str:
        span_id = str(uuid4())
        self.spans.append(SpanRecord(id=span_id, name=name, attrs=dict(attrs)))
        return span_id

    def end_span(self, span_id: str, **attrs: Any) -> None:
        for span in self.spans:
            if span.id == span_id:
                span.ended = True
                span.end_attrs = dict(attrs)
                return

    def event(self, name: str, **attrs: Any) -> None:
        self.events.append({"name": name, **attrs})


class NoOpTracer:
    def start_span(self, name: str, **attrs: Any) -> str:
        return "noop"

    def end_span(self, span_id: str, **attrs: Any) -> None:
        return None

    def event(self, name: str, **attrs: Any) -> None:
        return None
