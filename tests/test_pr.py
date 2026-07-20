"""PR builder: pure content derivation, incident round-trip, and dry-run safety.

Offline only — the git/gh push path is never exercised here (it is the outward-facing
action gated behind `--push`). We assert the pure builder, the JSON round-trip the CLI
relies on, and that dry-run / missing-input paths never touch git.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cassandra import pr
from cassandra.models import (
    ExperimentResult,
    FailureClass,
    Incident,
    ReplayResult,
    SpanRecord,
    Verdict,
)


def _incident(with_patch: bool = True) -> Incident:
    span = SpanRecord(
        span_id="U3Bhbjoz", trace_id="t1", project="patient-prod",
        started_at=datetime.now(timezone.utc),
        input_text="Refund window for Germany?",
        output_text="Germany has a 30-day return policy.",
    )
    inc = Incident.from_span(span)
    inc.verdict = Verdict(
        failure_class=FailureClass.HALLUCINATION, confidence=0.9,
        rationale="invented a policy get_refund_policy did not return",
    )
    inc.experiment = ExperimentResult(
        experiment_id="e1", baseline_pass_rate=0.0, candidate_pass_rate=1.0
    )
    inc.replay = ReplayResult(
        original_input="Refund window for Germany?",
        before_output="Germany has a 30-day return policy.",
        after_output="I couldn't find a policy for Germany; contact support.",
        fixed=True,
    )
    if with_patch:
        inc.candidate_prompt = "You are ShopBot. Never invent policy. Decline honestly."
        inc.prompt_diff = "--- current\n+++ candidate\n+Never invent policy."
    return inc


def test_build_pr_content_pure():
    content = pr.build_pr_content(_incident())
    assert "hallucination" in content.title
    assert f"[{_incident().incident_id}]" in content.title
    assert content.branch.startswith("cassandra/fix-")
    assert "0% → 100%" in content.body  # the pass-rate headline
    assert "FIXED" in content.body
    assert "Postmortem" in content.body  # the postmortem is embedded


def test_branch_is_slugged():
    inc = _incident()
    inc.incident_id = "inc-Weird/ID With Spaces!!"
    content = pr.build_pr_content(inc)
    # no path separators or spaces leak into the branch name
    assert "/" not in content.branch.removeprefix("cassandra/")
    assert " " not in content.branch


def test_load_incident_roundtrip(tmp_path):
    inc = _incident()
    (tmp_path / f"{inc.incident_id}.json").write_text(
        inc.model_dump_json(), encoding="utf-8"
    )
    loaded = pr.load_incident(inc.incident_id, reports_dir=tmp_path)
    assert loaded.incident_id == inc.incident_id
    assert loaded.candidate_prompt == inc.candidate_prompt
    assert loaded.verdict.failure_class is FailureClass.HALLUCINATION


def test_load_incident_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        pr.load_incident("nope", reports_dir=tmp_path)


def test_dry_run_changes_nothing(monkeypatch):
    # If dry-run touched git we'd know: make subprocess explode.
    monkeypatch.setattr(pr, "_run", lambda *a, **k: pytest.fail("git must not run on dry-run"))
    res = pr.open_pr(_incident(), dry_run=True)
    assert res.dry_run and not res.committed and not res.opened
    assert res.branch.startswith("cassandra/fix-")
    assert "dry run" in res.detail.lower()


def test_open_pr_requires_candidate_prompt():
    with pytest.raises(ValueError, match="no candidate prompt"):
        pr.open_pr(_incident(with_patch=False))


def test_open_pr_requires_prompt_file(monkeypatch):
    # candidate prompt present but no target file configured/passed.
    from cassandra.config import get_settings

    monkeypatch.setattr(get_settings(), "baseline_prompt_file", None)
    with pytest.raises(ValueError, match="prompt file"):
        pr.open_pr(_incident(), prompt_file=None)
