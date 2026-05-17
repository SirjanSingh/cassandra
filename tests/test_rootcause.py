"""Root-cause analyst with Gemini + MCP mocked (Killer Addition)."""

from datetime import datetime, timezone

import pytest

from cassandra.models import FailureClass, Incident, RootCause, SpanRecord, Verdict
from cassandra.rootcause import RootCauseAnalyst


class _Phx:
    def session(self):
        class _C:
            async def __aenter__(s):
                return s

            async def __aexit__(s, *a):
                return False

            async def annotate_span(s, **kw):
                return "ann-2"

        return _C()

    def span_url(self, span):
        return "http://phoenix/x"


def _inc() -> Incident:
    span = SpanRecord(
        span_id="s1", trace_id="t1", project="patient-prod",
        started_at=datetime.now(timezone.utc),
        input_text="refund policy for Germany?",
        output_text="90-day full cash refund.",
    )
    inc = Incident.from_span(span)
    inc.verdict = Verdict(
        failure_class=FailureClass.HALLUCINATION, confidence=0.93,
        rationale="Invented a policy.",
    )
    inc.annotation_id = "ann-1"
    return inc


@pytest.mark.asyncio
async def test_rootcause_enriches_incident(monkeypatch):
    async def fake_structured(prompt, schema, system=""):
        return RootCause(
            summary="Tool returned no policy; fragile prompt filled the gap.",
            culprit="get_refund_policy(region=DE) -> found=False",
            causal_chain=["tool miss", "no refuse rule", "model fabricates"],
            fix_strategy="Add explicit refuse-and-escalate when policy data is missing.",
        )

    monkeypatch.setattr("cassandra.rootcause.llm.structured", fake_structured)
    out = await RootCauseAnalyst(mcp=_Phx()).analyze(_inc())  # type: ignore[arg-type]
    assert out.root_cause is not None
    assert "get_refund_policy" in out.root_cause.culprit
    assert out.stage.value == "root_caused"
