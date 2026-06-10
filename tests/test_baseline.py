"""The baseline-prompt resolver is what makes the closed loop agent-agnostic:
file -> span(llm.input_messages) -> bundled demo Patient -> clear error."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

import pytest

from cassandra import baseline
from cassandra.baseline import BaselinePromptError, resolve_baseline_prompt
from cassandra.models import SpanRecord


def _span(attributes: dict | str) -> SpanRecord:
    return SpanRecord(
        span_id="s1",
        trace_id="t1",
        project="patient-prod",
        started_at=datetime.now(timezone.utc),
        input_text="hi",
        output_text="hello",
        raw={"attributes": attributes},
    )


def _settings(prompt_file: str | None):
    return type("S", (), {"baseline_prompt_file": prompt_file})()


def test_file_source_wins(tmp_path, monkeypatch):
    f = tmp_path / "prompt.txt"
    f.write_text("You are MyAgent. Be careful.", encoding="utf-8")
    monkeypatch.setattr(baseline, "get_settings", lambda: _settings(str(f)))
    span = _span({"llm.input_messages": [{"message": {"role": "system", "content": "other"}}]})
    assert resolve_baseline_prompt(span) == "You are MyAgent. Be careful."


def test_span_nested_messages(monkeypatch):
    monkeypatch.setattr(baseline, "get_settings", lambda: _settings(None))
    span = _span(
        {
            "llm.input_messages": [
                {"message": {"role": "system", "content": "You are TheirBot."}},
                {"message": {"role": "user", "content": "hi"}},
            ]
        }
    )
    assert resolve_baseline_prompt(span) == "You are TheirBot."


def test_span_json_encoded_messages(monkeypatch):
    monkeypatch.setattr(baseline, "get_settings", lambda: _settings(None))
    msgs = json.dumps([{"role": "system", "content": "You are JsonBot."}])
    span = _span({"llm.input_messages": msgs})
    assert resolve_baseline_prompt(span) == "You are JsonBot."


def test_span_flat_dotted_keys(monkeypatch):
    monkeypatch.setattr(baseline, "get_settings", lambda: _settings(None))
    span = _span(
        {
            "llm.input_messages.0.message.role": "system",
            "llm.input_messages.0.message.content": "You are FlatBot.",
        }
    )
    assert resolve_baseline_prompt(span) == "You are FlatBot."


def test_demo_fallback_to_shopbot(monkeypatch):
    monkeypatch.setattr(baseline, "get_settings", lambda: _settings(None))
    span = _span({"input.value": "hi"})  # no system message recorded
    from patient.agent import FRAGILE_SYSTEM_PROMPT

    assert resolve_baseline_prompt(span) == FRAGILE_SYSTEM_PROMPT


def test_clear_error_when_nothing_resolves(monkeypatch):
    monkeypatch.setattr(baseline, "get_settings", lambda: _settings(None))
    # Setting a sys.modules entry to None makes `from patient.agent import ...` raise
    # ImportError — simulates a deployment without the bundled demo Patient.
    monkeypatch.setitem(sys.modules, "patient.agent", None)
    with pytest.raises(BaselinePromptError, match="BASELINE_PROMPT_FILE"):
        resolve_baseline_prompt(_span({}))
