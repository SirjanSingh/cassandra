"""Unit tests for the schema-coupled MCP helpers (NFR-10 contract)."""

from cassandra.phoenix_mcp import _as_list, _id_of, normalize_span


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
    raw = {
        "context": {"span_id": "s1", "trace_id": "t1"},
        "start_time": "2026-05-17T00:00:00Z",
        "attributes": {"input": {"value": "hi"}, "output": {"value": "there"}},
    }
    s = normalize_span(raw, "patient-prod")
    assert s.span_id == "s1"
    assert s.trace_id == "t1"
    assert s.input_text == "hi"
    assert s.output_text == "there"
    assert s.project == "patient-prod"
