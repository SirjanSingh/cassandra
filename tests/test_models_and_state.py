"""Incident threading + dedupe state (FR-L3) and ExperimentResult delta (FR-E4)."""

from datetime import datetime, timezone

from cassandra.models import ExperimentResult, Incident, SpanRecord
from cassandra.state import LocalState


def _span(sid: str) -> SpanRecord:
    return SpanRecord(
        span_id=sid, trace_id="t", project="patient-prod",
        started_at=datetime.now(timezone.utc), input_text="q", output_text="a",
    )


def test_incident_identity_from_span():
    inc = Incident.from_span(_span("abc"))
    assert inc.incident_id == "inc-abc"
    assert inc.stage.value == "watched"


def test_experiment_delta():
    e = ExperimentResult(experiment_id="e1", baseline_pass_rate=0.25, candidate_pass_rate=0.92)
    assert e.delta == 0.67


def test_local_state_cursor_and_dedupe(tmp_path):
    st = LocalState(tmp_path / "s.json")
    assert st.get_cursor() is None
    now = datetime.now(timezone.utc)
    st.set_cursor(now)
    assert LocalState(tmp_path / "s.json").get_cursor() == now
    assert not st.seen("x")
    st.mark_seen("x")
    assert LocalState(tmp_path / "s.json").seen("x")
