"""CI prompt regression gate: offline tests (agent + judge mocked)."""

import json

import pytest

import cassandra.gate as gate
from cassandra.models import DatasetExample
from cassandra.oracle import Score

_CASES = [
    DatasetExample(
        input_text="refund window for Germany?",
        expected_answer="says the policy is unavailable",
        acceptance_criterion="no invented policy",
    ),
    DatasetExample(
        input_text="US refund policy?",
        expected_answer="30-day returns with receipt",
        acceptance_criterion="states the correct US policy",
    ),
]


def _mock_network(monkeypatch, verdicts: dict[str, bool]):
    """Patch the live-agent call and the pass/fail oracle with canned answers."""

    async def fake_ask(c, endpoint, message, prompt):
        return {"reply": f"reply to: {message}"}

    async def fake_judge(case, out):
        return Score(passed=verdicts[case.input_text], why="mocked")

    monkeypatch.setattr(gate, "_ask_agent", fake_ask)
    monkeypatch.setattr(gate, "_judge_case", fake_judge)


async def test_gate_passes_at_threshold(monkeypatch):
    _mock_network(monkeypatch, {c.input_text: True for c in _CASES})
    res = await gate.run_gate("PROMPT", _CASES, threshold=0.8)
    assert res.total == 2 and res.passed_cases == 2
    assert res.pass_rate == 1.0
    assert res.passed is True
    # computed field serializes (the MCP tool returns model_dump())
    assert res.model_dump()["passed"] is True


async def test_gate_fails_below_threshold(monkeypatch):
    _mock_network(
        monkeypatch,
        {_CASES[0].input_text: False, _CASES[1].input_text: True},
    )
    res = await gate.run_gate("PROMPT", _CASES, threshold=0.8)
    assert res.pass_rate == 0.5
    assert res.passed is False
    failed = [c for c in res.cases if not c.passed]
    assert failed[0].why == "mocked"


async def test_gate_empty_dataset(monkeypatch):
    _mock_network(monkeypatch, {})
    res = await gate.run_gate("PROMPT", [], threshold=0.8)
    assert res.total == 0 and res.pass_rate == 0.0 and res.passed is False


async def test_gate_scores_deterministically_when_ledger_present(monkeypatch):
    """B2: with a tool ledger in the reply, the gate needs no LLM judge at all."""

    async def boom(*a, **k):
        raise AssertionError("LLM judge must not be called on the deterministic path")

    monkeypatch.setattr("cassandra.llm.structured", boom)

    ledger = [
        {
            "name": "get_refund_policy",
            "args": {"region": "DE"},
            "result": {"found": False, "region": "DE", "policy": None},
        }
    ]

    async def fake_ask(c, endpoint, message, prompt):
        if "Germany" in message:
            return {"reply": "Germany has a 30-day return policy.", "tool_calls": ledger}
        return {
            "reply": "In the US we offer 30-day returns with receipt.",
            "tool_calls": [
                {
                    "name": "get_refund_policy",
                    "args": {"region": "US"},
                    "result": {"found": True, "region": "US", "policy": "30-day returns"},
                }
            ],
        }

    monkeypatch.setattr(gate, "_ask_agent", fake_ask)
    res = await gate.run_gate("PROMPT", _CASES, threshold=0.8)
    assert res.pass_rate == 0.5  # Germany fabrication fails, US grounded answer passes
    assert not res.cases[0].passed and res.cases[1].passed


def test_cli_exit_codes(monkeypatch, tmp_path, capsys):
    _mock_network(monkeypatch, {c.input_text: True for c in _CASES})
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("PROMPT", encoding="utf-8")
    cases_file = tmp_path / "cases.json"
    cases_file.write_text(
        json.dumps([c.model_dump() for c in _CASES]), encoding="utf-8"
    )

    with pytest.raises(SystemExit) as e:
        gate.main(
            ["--prompt-file", str(prompt_file), "--cases", str(cases_file), "--threshold", "0.8"]
        )
    assert e.value.code == 0
    assert "gate PASSED" in capsys.readouterr().out

    # now make every case fail -> exit 1
    _mock_network(monkeypatch, {c.input_text: False for c in _CASES})
    with pytest.raises(SystemExit) as e:
        gate.main(["--prompt-file", str(prompt_file), "--cases", str(cases_file), "--json"])
    assert e.value.code == 1
    assert '"passed": false' in capsys.readouterr().out
