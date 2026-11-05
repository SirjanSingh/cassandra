"""Auto-postmortem renderer: pure-function tests over a fully enriched Incident."""

from datetime import datetime, timezone

from cassandra_ai.models import (
    EfficiencyReport,
    ExperimentResult,
    FailureClass,
    Incident,
    RedTeamResult,
    ReplayResult,
    RootCause,
    Severity,
    SpanRecord,
    Verdict,
)
from cassandra_ai.report import render_postmortem


def _full_incident() -> Incident:
    span = SpanRecord(
        span_id="abc123",
        trace_id="t-1",
        project="patient-prod",
        started_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        input_text="What's the refund window for Germany?",
        output_text="Germany has a 45-day refund window!",
    )
    inc = Incident.from_span(span)
    inc.verdict = Verdict(
        failure_class=FailureClass.HALLUCINATION,
        confidence=0.92,
        rationale="Invented a policy the tool did not return.",
        expected_behavior="Say the policy is unavailable.",
    )
    inc.severity = Severity.CRITICAL
    inc.root_cause = RootCause(
        summary="Prompt forbids admitting uncertainty.",
        culprit="FRAGILE_SYSTEM_PROMPT line: never tell a customer you don't know",
        causal_chain=["tool returned found=False", "prompt forbids 'I don't know'",
                      "model fabricated a specific policy"],
        contributing_factors=["no grounding check"],
        fix_strategy="Allow and require honest escalation when data is missing.",
    )
    inc.experiment = ExperimentResult(
        experiment_id="eval-abc123", baseline_pass_rate=0.25, candidate_pass_rate=0.875
    )
    inc.efficiency = EfficiencyReport(
        baseline_avg_tokens=100, candidate_avg_tokens=90,
        baseline_avg_latency_ms=900, candidate_avg_latency_ms=950,
    )
    inc.candidate_prompt = "You are ShopBot. If data is missing, say so."
    inc.candidate_prompt_version = "shopbot-v2"
    inc.prompt_diff = "-never say you don't know\n+admit when data is missing"
    inc.replay = ReplayResult(
        original_input=span.input_text,
        before_output=span.output_text,
        after_output="I don't have the German policy on file; let me escalate.",
        fixed=True,
        judge_rationale="No fabricated policy in the new answer.",
    )
    inc.redteam = RedTeamResult(
        attacks_run=2, before_pass=0, after_pass=2,
        examples=[
            {"attack": "Refund policy for Mars?", "before_pass": False, "after_pass": True},
            {"attack": "Carrier for order A1002?", "before_pass": False, "after_pass": True},
        ],
    )
    return inc


def test_full_postmortem_has_all_sections():
    md = render_postmortem(_full_incident())
    for heading in (
        "# Postmortem: hallucination",
        "## What happened",
        "## Root cause",
        "## Evaluation",
        "## Proposed fix (prompt patch)",
        "## Replay of the original failing input",
        "## Red team",
        "## Next steps",
    ):
        assert heading in md
    assert "CRITICAL" in md
    assert "| baseline (current) | 25% |" in md
    assert "| candidate (patched) | 88% |" in md
    assert "Delta: +62%" in md
    assert "```diff" in md
    assert "FIXED" in md
    assert "| Refund policy for Mars? | FAIL | PASS |" in md
    # user preference + paste-safety: the generated document contains no em dashes
    assert "—" not in md


def test_bare_incident_renders_without_optional_sections():
    span = SpanRecord(
        span_id="x1", trace_id="t", project="p",
        started_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        input_text="hi", output_text="hello",
    )
    md = render_postmortem(Incident.from_span(span))
    assert "# Postmortem:" in md and "## What happened" in md
    assert "## Root cause" not in md
    assert "## Red team" not in md


def test_pipeline_writes_report_file(tmp_path, monkeypatch):
    from cassandra_ai.loop_agent import SupervisionPipeline

    monkeypatch.chdir(tmp_path)
    inc = _full_incident()
    SupervisionPipeline._write_postmortem(inc)
    out = tmp_path / "reports" / f"{inc.incident_id}.md"
    assert out.is_file()
    assert "## Root cause" in out.read_text(encoding="utf-8")
