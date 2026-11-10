"""Data shapes shared by every layer: one bot turn in, a verdict with findings out."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FailureClass(str, Enum):
    """Verdict classes of the deterministic tool-call rule (grounding.py)."""

    HALLUCINATION = "hallucination"  # stated a fact with no successful tool call behind it
    TOOL_FAILURE = "tool_failure"    # stated a field the tool returned empty
    OK = "ok"


class Turn(BaseModel):
    """One question → answer exchange of the bot being checked.

    The *source* is everything the bot was given to answer from: the results of its tool
    calls and/or retrieved documents (`context`). Cassandra checks the answer against it.
    """

    id: str = ""
    question: str = ""
    answer: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    context: str | list[Any] | dict[str, Any] | None = None

    def has_source(self) -> bool:
        return bool(self.tool_calls) or bool(self.context)

    def source(self) -> object:
        """What the bot was given, in the shape the checkers read.

        A lone context is passed through unchanged (a document stays a document);
        tool results and context together become one JSON-able object.
        """
        if not self.tool_calls:
            return self.context or ""
        calls = [{"tool": c.get("name"), "args": c.get("args"), "result": c.get("result")}
                 for c in self.tool_calls]
        return {"tool_calls": calls, "context": self.context} if self.context else calls


Layer = Literal["rule", "value", "claim"]
FindingKind = Literal[
    "no_tool_call",        # rule: a fact type that needs a tool, but no successful call
    "tool_returned_empty",  # rule: the tool returned that field empty
    "value_not_in_data",   # value: a number / time that appears nowhere in the source
    "contradicted",        # claim: the source says something different
    "not_in_source",       # claim: the source doesn't say it
]


class Finding(BaseModel):
    """One statement in the answer that the source does not back."""

    layer: Layer
    kind: FindingKind
    claim: str
    detail: str = ""


Verdict = Literal["flagged", "ok", "declined", "unchecked"]


class TurnResult(BaseModel):
    turn: Turn
    verdict: Verdict
    findings: list[Finding] = Field(default_factory=list)
    layers: list[Layer] = Field(default_factory=list)  # which checks actually ran
    note: str = ""  # why a turn is unchecked / declined


class Report(BaseModel):
    source: str
    layers: list[Layer]
    model: str | None = None
    results: list[TurnResult]

    def count(self, verdict: Verdict) -> int:
        return sum(r.verdict == verdict for r in self.results)
