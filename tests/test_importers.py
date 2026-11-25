"""cassandra_ai/importers.py and conversation rows in scan.load_turns."""

from __future__ import annotations

import json

from cassandra_ai.importers import turns_from_messages
from cassandra_ai.scan import load_turns

OPENAI_CONV = [
    {"role": "system", "content": "You are a shop assistant."},
    {"role": "user", "content": "Where is order A1?"},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function",
         "function": {"name": "lookup_order", "arguments": '{"id": "A1"}'}}]},
    {"role": "tool", "tool_call_id": "c1", "content": '{"found": true, "carrier": "UPS"}'},
    {"role": "assistant", "content": "It ships with UPS."},
    {"role": "user", "content": [{"type": "text", "text": "Thanks!"}]},
    {"role": "assistant", "content": "You're welcome."},
]


def test_openai_conversation_becomes_one_turn_per_text_reply():
    turns = turns_from_messages(OPENAI_CONV, "c")
    assert [t.id for t in turns] == ["c#1", "c#2"]
    first, second = turns
    assert first.question == "Where is order A1?" and first.answer == "It ships with UPS."
    assert first.tool_calls == [{"name": "lookup_order", "args": {"id": "A1"},
                                 "result": {"found": True, "carrier": "UPS"}}]
    assert second.question == "Thanks!" and second.tool_calls == []


def test_python_repr_tool_calls_and_inline_call_markup():
    msgs = [
        {"role": "user", "content": "Cancel W1"},
        {"role": "assistant", "content": "None",
         "tool_calls": "[{'id': '0', 'function': {'name': 'cancel', 'arguments': {'id': 'W1'}}}]"},
        {"role": "tool", "tool_call_id": "0", "name": "cancel", "content": "Error: not pending"},
        {"role": "assistant", "content": "Sorry. <function_calls><invoke/></function_calls>"},
    ]
    (turn,) = turns_from_messages(msgs)
    assert turn.answer == "Sorry."
    assert turn.tool_calls == [{"name": "cancel", "args": {"id": "W1"},
                                "result": "Error: not pending"}]


def test_results_without_ids_match_in_order():
    msgs = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "tool_calls": [{"function": {"name": "a", "arguments": "{}"}},
                                             {"function": {"name": "b", "arguments": "{}"}}]},
        {"role": "tool", "name": "a", "content": "1"},
        {"role": "tool", "name": "b", "content": "2"},
        {"role": "assistant", "content": "ok"},
    ]
    (turn,) = turns_from_messages(msgs)
    assert [(c["name"], c["result"]) for c in turn.tool_calls] == [("a", 1), ("b", 2)]


def test_scan_reads_conversation_rows_and_json_lists(tmp_path):
    jsonl = tmp_path / "convs.jsonl"
    jsonl.write_text(json.dumps({"id": "c", "messages": OPENAI_CONV}) + "\n"
                     + json.dumps({"id": "t", "question": "q", "answer": "a"}) + "\n",
                     encoding="utf-8")
    assert [t.id for t in load_turns(jsonl)] == ["c#1", "c#2", "t"]

    as_list = tmp_path / "convs.json"
    as_list.write_text(json.dumps([{"task_id": 7, "traj": OPENAI_CONV}], indent=2),
                       encoding="utf-8")
    assert [t.id for t in load_turns(as_list)] == ["7#1", "7#2"]
