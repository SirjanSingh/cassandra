"""Diagnostician logic with Gemini + Phoenix MCP mocked (offline, FR-D1/D3).

Validates the decision boundary: a high-confidence failure annotates the span;
a low-confidence or OK verdict does not. Real classification quality (AC-8, the
20-case trap set) is a live integration check, not a unit test.
"""

import json

import pytest

from cassandra.diagnostician import Diagnostician
from cassandra.models import FailureClass, Incident, SpanRecord, Verdict
from cassandra.phoenix_mcp import normalize_span


class _FakePhx:
    def __init__(self):
        self.annotated = []

    def session(self):
        outer = self

        class _Ctx:
            async def __aenter__(self_):
                return self_

            async def __aexit__(self_, *a):
                return False

            async def annotate_span(self_, **kw):
                outer.annotated.append(kw)
                return "ann-1"

        return _Ctx()

    def span_url(self, span):
        return "http://phoenix/x"


def _span():
    from datetime import datetime, timezone

    return SpanRecord(
        span_id="s1", trace_id="t1", project="patient-prod",
        started_at=datetime.now(timezone.utc),
        input_text="refund policy for Germany?",
        output_text="Sure! 90-day full cash refund, no receipt needed.",
    )


@pytest.mark.asyncio
async def test_high_confidence_failure_is_annotated(monkeypatch):
    async def fake_structured(prompt, schema, system="", temperature=0.2):
        return Verdict(
            failure_class=FailureClass.HALLUCINATION, confidence=0.93,
            rationale="Invented a refund policy with no supporting tool data.",
        )

    monkeypatch.setattr("cassandra.diagnostician.llm.structured", fake_structured)
    phx = _FakePhx()
    d = Diagnostician(mcp=phx)  # type: ignore[arg-type]
    inc = await d.diagnose(Incident.from_span(_span()))
    assert inc.verdict.failure_class is FailureClass.HALLUCINATION
    assert inc.annotation_id == "ann-1"
    assert phx.annotated and phx.annotated[0]["label"] == "hallucination"


@pytest.mark.asyncio
async def test_ok_verdict_not_annotated(monkeypatch):
    async def fake_structured(prompt, schema, system="", temperature=0.2):
        return Verdict(failure_class=FailureClass.OK, confidence=0.99, rationale="grounded")

    monkeypatch.setattr("cassandra.diagnostician.llm.structured", fake_structured)
    phx = _FakePhx()
    inc = await Diagnostician(mcp=phx).diagnose(Incident.from_span(_span()))  # type: ignore[arg-type]
    assert inc.annotation_id is None
    assert not phx.annotated


@pytest.mark.asyncio
async def test_production_path_feeds_tool_ledger_to_judge(monkeypatch):
    """F1 regression: the PRODUCTION path (normalize_span -> diagnose) must reach the judge
    with the structured tool ledger, not just the self-eval HTTP path. Pre-fix the ledger
    was dropped and this prompt contained 'TOOL CALLS (...): none'.
    """
    ledger = [
        {"name": "get_refund_policy", "args": {"region": "DE"}, "result": {"found": False}}
    ]
    raw = {
        "context": {"span_id": "s9", "trace_id": "t9"},
        "start_time": "2026-05-17T00:00:00Z",
        "attributes": {
            "input.value": "refund window for Germany?",
            "output.value": "Germany has a 30-day refund policy.",
            "tool.calls": json.dumps(ledger),  # the Patient's real shape: nested JSON string
        },
    }
    span = normalize_span(raw, "patient-prod")
    assert span.tool_calls, "precondition: normalize_span must surface the ledger"

    captured: dict = {}

    async def fake_structured(prompt, schema, system="", temperature=0.2):
        captured["prompt"] = prompt
        return Verdict(
            failure_class=FailureClass.HALLUCINATION, confidence=0.9, rationale="ungrounded"
        )

    monkeypatch.setattr("cassandra.diagnostician.llm.structured", fake_structured)
    await Diagnostician(mcp=_FakePhx()).diagnose(Incident.from_span(span))  # type: ignore[arg-type]

    prompt = captured["prompt"]
    assert "get_refund_policy" in prompt
    assert "found" in prompt and "false" in prompt.lower()
    assert "none" not in prompt.split("TOOL CALLS")[1][:40].lower()
