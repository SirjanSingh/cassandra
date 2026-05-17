"""Shared domain models that thread through the supervision pipeline.

The `Incident` object is the single piece of state passed Watcher -> Patcher
(ARCHITECTURE.md S2). Each sub-agent enriches it and passes it on.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FailureClass(str, Enum):
    HALLUCINATION = "hallucination"
    PROMPT_DRIFT = "prompt_drift"
    TOOL_FAILURE = "tool_failure"
    OK = "ok"


class SpanRecord(BaseModel):
    """A normalized view of a Phoenix span tree (root LLM span + child tool spans).

    SPIKE-RECONCILE: field mapping depends on the exact Phoenix MCP span schema;
    `phoenix_mcp.normalize_span` is the only place that needs to change.
    """

    span_id: str
    trace_id: str
    project: str
    started_at: datetime
    input_text: str = ""
    output_text: str = ""
    tool_calls: list[dict] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class Verdict(BaseModel):
    """Diagnostician output (FR-D1, FR-D2)."""

    failure_class: FailureClass
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    expected_behavior: str = ""

    @property
    def is_failure(self) -> bool:
        return self.failure_class is not FailureClass.OK


class RootCause(BaseModel):
    """Structured causal analysis of a failure (Killer Addition: root-cause analysis).

    Goes beyond "what failed" to "why" - the causal chain a Phoenix judge wants.
    """

    summary: str
    culprit: str  # the span/tool/prompt element that triggered the failure
    causal_chain: list[str]  # ordered steps from trigger to bad output
    contributing_factors: list[str] = Field(default_factory=list)
    fix_strategy: str  # what kind of change prevents recurrence (feeds the Patcher)


class DatasetExample(BaseModel):
    """One synthesized adversarial probe (FR-S1)."""

    input_text: str
    expected_answer: str
    acceptance_criterion: str


class ExperimentResult(BaseModel):
    """Evaluator output (FR-E4)."""

    experiment_id: str
    baseline_pass_rate: float
    candidate_pass_rate: float | None = None

    @property
    def delta(self) -> float | None:
        if self.candidate_pass_rate is None:
            return None
        return round(self.candidate_pass_rate - self.baseline_pass_rate, 4)


class ReplayResult(BaseModel):
    """Live trace replay: the ORIGINAL failing input re-run on the patched prompt."""

    original_input: str
    before_output: str  # the recorded hallucination
    after_output: str  # the patched agent's answer to the same input
    fixed: bool  # judge verdict: did the patch actually fix this exact case?
    judge_rationale: str = ""


class RedTeamResult(BaseModel):
    """Adversarial testing: synthesized attacks fired at the live Patient."""

    attacks_run: int
    before_pass: int  # passes under the current (fragile) prompt
    after_pass: int  # passes under the candidate prompt
    examples: list[dict] = Field(default_factory=list)


class Stage(str, Enum):
    WATCHED = "watched"
    DIAGNOSED = "diagnosed"
    ROOT_CAUSED = "root_caused"
    SYNTHESIZED = "synthesized"
    EVALUATED = "evaluated"
    PATCHED = "patched"
    REPLAYED = "replayed"
    RED_TEAMED = "red_teamed"


class Incident(BaseModel):
    """Threads through the whole pipeline. Identity = offending span_id (FR-L3 dedupe)."""

    incident_id: str
    span: SpanRecord
    created_at: datetime = Field(default_factory=_now)
    stage: Stage = Stage.WATCHED

    verdict: Verdict | None = None
    root_cause: RootCause | None = None
    annotation_id: str | None = None
    dataset_id: str | None = None
    dataset_examples: list[DatasetExample] = Field(default_factory=list)
    experiment: ExperimentResult | None = None
    candidate_prompt: str | None = None
    candidate_prompt_version: str | None = None
    prompt_diff: str | None = None
    replay: ReplayResult | None = None
    redteam: RedTeamResult | None = None

    @classmethod
    def from_span(cls, span: SpanRecord) -> "Incident":
        return cls(incident_id=f"inc-{span.span_id}", span=span)


class PipelineEvent(BaseModel):
    """Streamed to the dashboard SSE feed (FR-DB1, FR-L2)."""

    incident_id: str
    stage: Stage
    at: datetime = Field(default_factory=_now)
    title: str
    detail: str = ""
    phoenix_url: str | None = None
    payload: dict = Field(default_factory=dict)
