"""Offline tests for severity, efficiency, Phoenix-experiments guard, self-tracing."""

from cassandra.models import (
    EfficiencyReport,
    FailureClass,
    Severity,
    Verdict,
    compute_severity,
)


def _v(fc: FailureClass, c: float) -> Verdict:
    return Verdict(failure_class=fc, confidence=c, rationale="x")


def test_compute_severity_tiers():
    assert compute_severity(_v(FailureClass.OK, 0.99)) == Severity.LOW
    assert compute_severity(_v(FailureClass.HALLUCINATION, 0.9)) == Severity.CRITICAL
    assert compute_severity(_v(FailureClass.TOOL_FAILURE, 0.72)) == Severity.HIGH
    assert compute_severity(_v(FailureClass.PROMPT_DRIFT, 0.55)) == Severity.MEDIUM
    assert compute_severity(_v(FailureClass.HALLUCINATION, 0.3)) == Severity.LOW


def test_efficiency_deltas():
    e = EfficiencyReport(
        baseline_avg_tokens=100, candidate_avg_tokens=80,
        baseline_avg_latency_ms=200, candidate_avg_latency_ms=250,
    )
    assert e.token_delta_pct == -0.2     # 20% cheaper
    assert e.latency_delta_pct == 0.25   # 25% slower
    assert EfficiencyReport().token_delta_pct is None  # zero baseline -> undefined


def test_register_experiment_flag_off(monkeypatch):
    import cassandra.phoenix_experiments as pe

    monkeypatch.setattr(pe, "get_settings", lambda: type("S", (), {"phoenix_experiments_enabled": False})())
    assert pe.register_experiment("ds", "prompt", "baseline") is None


def test_register_experiment_success_and_degradation(monkeypatch):
    import cassandra.phoenix_experiments as pe

    monkeypatch.setattr(pe, "get_settings", lambda: type("S", (), {"phoenix_experiments_enabled": True})())

    monkeypatch.setattr(pe, "_run", lambda *a: "http://phx/experiments/1")
    assert pe.register_experiment("ds", "prompt", "candidate") == "http://phx/experiments/1"

    def boom(*a):
        raise RuntimeError("phoenix down")

    monkeypatch.setattr(pe, "_run", boom)
    assert pe.register_experiment("ds", "prompt", "baseline") is None  # degrades, never raises


def test_self_tracing_respects_flag(monkeypatch):
    import cassandra.instrumentation as ins

    ins._INITIALIZED = False
    monkeypatch.setattr(ins, "get_settings", lambda: type("S", (), {"self_trace_enabled": False})())
    assert ins.init_self_tracing() is False
