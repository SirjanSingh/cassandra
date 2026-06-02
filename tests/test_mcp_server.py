"""Offline tests for the custom cassandra-mcp server (no network)."""

from datetime import datetime, timezone

import pytest

from cassandra import mcp_server
from cassandra.models import (
    DatasetExample,
    ExperimentResult,
    FailureClass,
    Incident,
    RedTeamResult,
    ReplayResult,
    RootCause,
    SpanRecord,
    Verdict,
)


def _full_incident() -> Incident:
    span = SpanRecord(
        span_id="s1", trace_id="t1", project="patient-prod",
        started_at=datetime.now(timezone.utc),
        input_text="refund policy for Germany?",
        output_text="Sure! 90-day full cash refund.",
    )
    inc = Incident.from_span(span)
    inc.verdict = Verdict(
        failure_class=FailureClass.HALLUCINATION, confidence=0.93,
        rationale="Invented a policy with no tool data.",
    )
    inc.root_cause = RootCause(
        summary="No policy data for DE; prompt never refuses.",
        culprit="get_refund_policy returned empty",
        causal_chain=["tool miss", "prompt gap", "fabrication"],
        fix_strategy="Refuse + escalate when policy data is missing.",
    )
    inc.dataset_examples = [
        DatasetExample(input_text="refund for France?", expected_answer="refuse",
                       acceptance_criterion="does not fabricate")
    ]
    inc.experiment = ExperimentResult(
        experiment_id="eval-s1", baseline_pass_rate=0.25, candidate_pass_rate=1.0
    )
    inc.candidate_prompt = "…hardened…"
    inc.candidate_prompt_version = "patient-shopbot-system-v2"
    inc.prompt_diff = "--- current\n+++ candidate\n+Refuse when policy missing."
    inc.replay = ReplayResult(
        original_input="refund policy for Germany?",
        before_output="Sure! 90-day…", after_output="I can't confirm that; escalating.",
        fixed=True,
    )
    inc.redteam = RedTeamResult(attacks_run=6, before_pass=1, after_pass=6)
    return inc


def test_report_serializes_full_incident():
    r = mcp_server._report(_full_incident())
    assert r["span_id"] == "s1"
    assert r["verdict"]["failure_class"] == "hallucination"
    assert r["root_cause"]["culprit"].startswith("get_refund_policy")
    assert r["evaluation"]["delta"] == 0.75
    assert r["patch"]["candidate_prompt_version"] == "patient-shopbot-system-v2"
    assert r["replay"]["fixed"] is True
    assert r["red_team"]["after_pass"] == 6
    assert r["dataset_size"] == 1


@pytest.mark.asyncio
async def test_tools_are_registered():
    tools = {t.name for t in await mcp_server.mcp.list_tools()}
    assert {"diagnose", "synthesize_evals", "propose_patch", "supervise_latest"} <= tools
