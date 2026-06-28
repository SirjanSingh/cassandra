"""Unit tests for the schema-coupled MCP helpers (NFR-10 contract)."""

import json

from cassandra.phoenix_mcp import _as_list, _extract_tool_calls, _id_of, normalize_span


def test_id_of_extracts_known_keys():
    assert _id_of({"dataset_id": "ds-1"}, "fb") == "ds-1"
    assert _id_of({"id": 42}, "fb") == "42"
    assert _id_of("exp-9", "fb") == "exp-9"
    assert _id_of({"unrelated": 1}, "fallback") == "fallback"


def test_as_list_unwraps_envelopes():
    assert _as_list({"spans": [1, 2]}) == [1, 2]
    assert _as_list([3]) == [3]
    assert _as_list(None) == []


def test_normalize_span_maps_core_fields():
    # The Patient emits FLAT dotted OpenInference attributes (patient/agent.py:
    # span.set_attribute("input.value", ...)), which normalize_span reads directly.
    raw = {
        "context": {"span_id": "s1", "trace_id": "t1"},
        "start_time": "2026-05-17T00:00:00Z",
        "attributes": {"input.value": "hi", "output.value": "there"},
    }
    s = normalize_span(raw, "patient-prod")
    assert s.span_id == "s1"
    assert s.trace_id == "t1"
    assert s.input_text == "hi"
    assert s.output_text == "there"
    assert s.project == "patient-prod"


def test_normalize_span_handles_nested_attributes():
    # Some Phoenix MCP builds return attributes NESTED rather than flat-dotted.
    # normalize_span must still extract input/output, else the Watcher silently
    # drops the span (no input/output text => not a candidate tree).
    raw = {
        "context": {"span_id": "s2", "trace_id": "t2"},
        "start_time": "2026-05-17T00:00:00Z",
        "attributes": {"input": {"value": "hi"}, "output": {"value": "there"}},
    }
    s = normalize_span(raw, "patient-prod")
    assert s.input_text == "hi"
    assert s.output_text == "there"


# --- F1 regression: the production tool-ledger oracle ---
# These guard the bug where the Diagnostician judged production turns with NO tool results,
# because normalize_span read a top-level "tool_calls" key that never existed while the
# Patient emits the ledger as a JSON string under attributes["tool.calls"].

_LEDGER = [
    {"name": "get_refund_policy", "args": {"region": "DE"}, "result": {"found": False}}
]


def test_normalize_span_extracts_tool_ledger_from_json_string():
    # The Patient's real shape: tool.calls is a JSON STRING nested in attributes.
    raw = {
        "context": {"span_id": "s3", "trace_id": "t3"},
        "start_time": "2026-05-17T00:00:00Z",
        "attributes": {
            "input.value": "refund window for Germany?",
            "output.value": "Germany has a 30-day refund policy.",
            "tool.calls": json.dumps(_LEDGER),
        },
    }
    s = normalize_span(raw, "patient-prod")
    assert s.tool_calls, "tool ledger must reach the production SpanRecord (F1)"
    assert s.tool_calls[0]["name"] == "get_refund_policy"
    assert s.tool_calls[0]["result"] == {"found": False}


def test_normalize_span_extracts_tool_ledger_when_already_list():
    raw = {
        "context": {"span_id": "s4", "trace_id": "t4"},
        "start_time": "2026-05-17T00:00:00Z",
        "attributes": {"input.value": "hi", "output.value": "x", "tool.calls": _LEDGER},
    }
    s = normalize_span(raw, "patient-prod")
    assert s.tool_calls[0]["name"] == "get_refund_policy"


def test_extract_tool_calls_handles_openinference_and_garbage():
    # Nested OpenInference shape.
    assert _extract_tool_calls({"tool": {"calls": _LEDGER}}) == _LEDGER
    # llm.tool_calls fallback key.
    assert _extract_tool_calls({"llm.tool_calls": _LEDGER}) == _LEDGER
    # Total robustness: never raises, always a list.
    assert _extract_tool_calls({}) == []
    assert _extract_tool_calls({"tool.calls": "not json"}) == []
    assert _extract_tool_calls({"tool.calls": 42}) == []
