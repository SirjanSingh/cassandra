"""Log loading, the 3-layer check engine, and reports. LLM always mocked."""

from __future__ import annotations

import json

import pytest

from cassandra import engine as check_mod
from cassandra.engine import check_many, check_offline, check_turn
from cassandra.faithfulness import Claim, ClaimReport
from cassandra.grounding import GroundingSpec, LookupRule
from cassandra.models import Report, Turn
from cassandra.report import render_html, render_json, render_markdown
from cassandra.scan import load_turns

SPEC = GroundingSpec(
    lookups=[LookupRule(tool="get_fee", claims=["money"])],
    decline_markers=["couldn't find"],
    claim_extractors={"money": r"\$\d+"},
)
FOUND = {"name": "get_fee", "args": {}, "result": {"found": True, "fee": 45}}
MISSING = {"name": "get_fee", "args": {}, "result": {"found": False}}


def _fake_claims(*unsupported: str):
    async def fake(question, answer, source):
        return ClaimReport(claims=[Claim(claim=c, status="contradicted", evidence="src says x")
                                   for c in unsupported])
    return fake


# --- loading ---------------------------------------------------------------

def test_load_accepts_aliases_and_context(tmp_path):
    p = tmp_path / "logs.jsonl"
    p.write_text("\n".join([
        json.dumps({"id": "a", "input": "q", "reply": "r", "tools": [FOUND]}),
        json.dumps({"user": "q2", "output": "r2", "documents": ["doc one"]}),
        "",
    ]), encoding="utf-8")
    a, b = load_turns(p)
    assert (a.id, a.question, a.answer, len(a.tool_calls)) == ("a", "q", "r", 1)
    assert b.id == "2" and b.context == ["doc one"] and b.has_source()


@pytest.mark.parametrize("line,msg", [
    ("not json", "line 1: not valid JSON"),
    ('{"question": "q"}', "line 1: no answer field"),
    ('{"answer": "a", "tool_calls": {}}', "line 1: tool_calls must be a list"),
    ("[1, 2]", "line 1: expected a JSON object"),
])
def test_load_names_the_bad_line(tmp_path, line, msg):
    p = tmp_path / "bad.jsonl"
    p.write_text(line, encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        load_turns(p)


# --- offline layers ----------------------------------------------------------

def test_rule_flags_a_fact_with_no_successful_tool_call():
    r = check_offline(Turn(answer="The fee is $45.", tool_calls=[MISSING]), SPEC)
    assert r.verdict == "flagged" and r.findings[0].layer == "rule"
    assert r.findings[0].kind == "no_tool_call"


def test_backed_answer_is_ok_and_decline_is_declined():
    assert check_offline(Turn(answer="The fee is $45.", tool_calls=[FOUND]), SPEC).verdict == "ok"
    r = check_offline(Turn(answer="Sorry, I couldn't find that.", tool_calls=[MISSING]), SPEC)
    assert r.verdict == "declined"


def test_value_layer_catches_a_wrong_number_without_a_spec():
    r = check_offline(Turn(answer="The fee is 54 dollars.", tool_calls=[FOUND]))
    assert r.verdict == "flagged" and r.findings[0].layer == "value"
    assert r.findings[0].claim == "54"


def test_numbers_from_the_question_dates_and_rounding_are_not_flagged():
    t = Turn(question="Rate for 600 GBP on 2016-06-24?",
             answer="On June 24, 600 pounds was about 797.3 dollars at 1.3288.",
             tool_calls=[{"name": "fx", "args": {"date": "2016-06-24"},
                          "result": {"rate": 1.32883, "converted": 797.28}}])
    assert check_offline(t).verdict == "ok"


def test_no_source_means_unchecked_not_ok():
    r = check_offline(Turn(answer="It costs $45."))
    assert r.verdict == "unchecked" and "nothing to check" in r.note


# --- claim layer -------------------------------------------------------------

async def test_claim_layer_adds_findings(monkeypatch):
    monkeypatch.setattr(check_mod, "claim_check", _fake_claims("Ships via FedEx"))
    r = await check_turn(Turn(answer="Ships via FedEx.", context="Carrier: UPS"))
    assert r.verdict == "flagged" and r.layers == ["value", "claim"]
    assert (r.findings[0].layer, r.findings[0].kind) == ("claim", "contradicted")


async def test_claim_layer_skipped_without_source_or_when_declined(monkeypatch):
    async def boom(*a):
        raise AssertionError("LLM must not be called")
    monkeypatch.setattr(check_mod, "claim_check", boom)
    assert (await check_turn(Turn(answer="It is $45."))).verdict == "unchecked"
    declined = Turn(answer="Sorry, I couldn't find that.", tool_calls=[MISSING])
    assert (await check_turn(declined, SPEC)).verdict == "declined"
    assert (await check_turn(Turn(answer="ok", context="x"), use_llm=False)).layers == ["value"]


async def test_check_many_keeps_order_and_reports_progress(monkeypatch):
    monkeypatch.setattr(check_mod, "claim_check", _fake_claims())
    seen = []
    turns = [Turn(id=str(i), answer="fine", context="fine") for i in range(5)]
    out = await check_many(turns, concurrency=2, on_done=lambda d, n: seen.append((d, n)))
    assert [r.turn.id for r in out] == ["0", "1", "2", "3", "4"]
    assert seen[-1] == (5, 5)


# --- reports -----------------------------------------------------------------

def _report(layers=("value",)) -> Report:
    bad = check_offline(Turn(id="t<1>", question="Fee?", answer="It is 54 <b>dollars</b>.",
                             tool_calls=[FOUND]))
    ok = check_offline(Turn(id="t2", answer="It is 45.", tool_calls=[FOUND]))
    return Report(source="logs.jsonl", layers=list(layers), results=[bad, ok])


def test_html_report_is_escaped_and_self_contained():
    out = render_html(_report())
    assert "<b>dollars</b>" not in out and "&lt;b&gt;dollars&lt;/b&gt;" in out
    assert "1 of 2 answers (50%)" in out and "Not in the data" in out
    assert "rerun with --llm" in out  # offline report says what it skipped
    assert "<script" not in out and "http://" not in out


def test_markdown_and_json_reports():
    md = render_markdown(_report(layers=("value", "claim")))
    assert md.startswith("# Cassandra answer check") and "--llm" not in md
    data = json.loads(render_json(_report()))
    assert data["results"][0]["verdict"] == "flagged"
