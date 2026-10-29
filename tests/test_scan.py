"""`cassandra scan`: offline log scanning with the grounding rule (LLM mocked)."""

from __future__ import annotations

import json

import pytest

from cassandra import cli, scan
from cassandra.grounding import GroundingSpec, LookupRule
from cassandra.models import FailureClass, Verdict

SPEC = GroundingSpec(
    lookups=[LookupRule(tool="get_fee", claims=["money"])],
    decline_markers=["couldn't find"],
    claim_extractors={"money": r"\$\d+"},
)
FOUND = {"name": "get_fee", "args": {}, "result": {"found": True, "fee": 45}}
MISSING = {"name": "get_fee", "args": {}, "result": {"found": False}}


def _write(tmp_path, rows):
    p = tmp_path / "logs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_load_turns_accepts_aliases_and_skips_blank_lines(tmp_path):
    p = tmp_path / "logs.jsonl"
    p.write_text(
        json.dumps({"input": "q1", "reply": "a1"}) + "\n\n"
        + json.dumps({"id": "x", "message": "q2", "output": "a2", "tools": [FOUND]}) + "\n",
        encoding="utf-8",
    )
    turns = scan.load_turns(p)
    assert [(t.id, t.question, t.answer) for t in turns] == [("1", "q1", "a1"), ("x", "q2", "a2")]
    assert turns[1].tool_calls == [FOUND]


@pytest.mark.parametrize("line,msg", [
    ("{not json", "line 1: not valid JSON"),
    (json.dumps({"question": "q"}), "line 1: no answer field"),
    (json.dumps({"answer": "a", "tool_calls": {}}), "line 1: tool_calls must be a list"),
])
def test_load_turns_rejects_bad_lines(tmp_path, line, msg):
    p = tmp_path / "logs.jsonl"
    p.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        scan.load_turns(p)


@pytest.mark.parametrize("answer,calls,status", [
    ("The wire fee is $25.", [MISSING], "unsupported"),
    ("The wire fee is $45.", [FOUND], "ok"),
    ("Sorry, I couldn't find the fee.", [MISSING], "declined"),
    ("Fees vary by account type.", [], "undecided"),
])
def test_check_turn_statuses(answer, calls, status):
    r = scan.check_turn(scan.Turn(id="t", answer=answer, tool_calls=calls), SPEC)
    assert r.status == status and r.layer == "rule"


@pytest.mark.asyncio
async def test_rule_only_never_calls_the_llm(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("LLM must not be called in rule-only mode")

    monkeypatch.setattr("cassandra.llm.structured", boom)
    turns = [scan.Turn(id="t", answer="Fees vary.", tool_calls=[])]
    assert [r.status for r in await scan.scan(turns, SPEC)] == ["undecided"]


@pytest.mark.asyncio
async def test_judge_decides_only_undecided_turns(monkeypatch):
    seen: list[str] = []

    async def fake_structured(prompt, schema, system="", temperature=0.0):
        seen.append(prompt)
        return Verdict(failure_class=FailureClass.HALLUCINATION, confidence=0.9, rationale="made up")

    monkeypatch.setattr("cassandra.diagnostician.llm.structured", fake_structured)
    turns = [
        scan.Turn(id="a", answer="The wire fee is $45.", tool_calls=[FOUND]),
        scan.Turn(id="b", answer="Fees vary by account.", tool_calls=[]),
    ]
    results = await scan.scan(turns, SPEC, judge=True)
    assert [(r.status, r.layer) for r in results] == [("ok", "rule"), ("unsupported", "llm")]
    assert len(seen) == 1 and "Fees vary" in seen[0]


def test_render_markdown_headline_and_examples():
    turns = [
        scan.Turn(id="a", question="wire fee?", answer="It is $25.", tool_calls=[MISSING]),
        scan.Turn(id="b", question="fee?", answer="It is $45.", tool_calls=[FOUND]),
        scan.Turn(id="c", answer="Fees vary.", tool_calls=[]),
    ]
    report = scan.ScanReport(source="logs.jsonl", mode="rule only, no LLM",
                             results=[scan.check_turn(t, SPEC) for t in turns])
    md = scan.render_markdown(report)
    assert "**1 of 3 answers (33%) stated a specific fact that no tool call backed.**" in md
    assert "### 1. `a` — wire fee?" in md and "- Claim: `$25`" in md
    assert "## Not checkable" in md and "`c`" in md


def test_cli_scan_writes_report(tmp_path, capsys):
    logs = _write(tmp_path, [{"question": "fee?", "answer": "It is $25.", "tool_calls": [MISSING]}])
    spec = tmp_path / "spec.json"
    spec.write_text(SPEC.model_dump_json(), encoding="utf-8")
    out, js = tmp_path / "r.md", tmp_path / "r.json"
    with pytest.raises(SystemExit) as e:
        cli.main(["scan", str(logs), "--spec", str(spec), "--out", str(out), "--json", str(js)])
    assert e.value.code == 0
    assert "1 of 1 answers stated a fact no tool backed" in capsys.readouterr().out
    assert "Unsupported fact | 1" in out.read_text(encoding="utf-8")
    assert json.loads(js.read_text(encoding="utf-8"))[0]["status"] == "unsupported"


def test_cli_scan_requires_a_spec(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("cassandra.config.get_settings",
                        lambda: type("S", (), {"grounding_spec_file": None})())
    logs = _write(tmp_path, [{"answer": "a"}])
    with pytest.raises(SystemExit) as e:
        cli.main(["scan", str(logs)])
    assert e.value.code == 2
    assert "grounding spec" in capsys.readouterr().err
