"""The `cassandra` command, the SDK entry point, and the HTTP API. LLM always mocked."""

from __future__ import annotations

import json

import pytest

import cassandra
from cassandra import engine as check_mod
from cassandra import cli
from cassandra.config import reload_settings
from cassandra.faithfulness import Claim, ClaimReport


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    """Tests never see a real key, whatever the developer's .env says."""
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.delenv("CASSANDRA_API_KEY", raising=False)
    reload_settings()
    yield
    reload_settings()


def _run(argv):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    return e.value.code


def test_no_args_prints_banner_and_commands(capsys):
    assert _run([]) == 0
    out = capsys.readouterr().out
    assert "demo" in out and "scan" in out and "serve" in out


def test_demo_writes_an_html_report_offline(tmp_path, capsys):
    out = tmp_path / "demo.html"
    assert _run(["demo", "--out", str(out)]) == 0
    assert "of 50 answers" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8").startswith("<!doctype html>")


def _logs(tmp_path):
    p = tmp_path / "logs.jsonl"
    rows = [{"id": "1", "question": "Fee?", "answer": "It is 54.",
             "tool_calls": [{"name": "fee", "args": {}, "result": {"fee": 45}}]},
            {"id": "2", "question": "Fee?", "answer": "It is 45.",
             "tool_calls": [{"name": "fee", "args": {}, "result": {"fee": 45}}]}]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_scan_writes_markdown_and_json(tmp_path, capsys):
    out, js = tmp_path / "r.md", tmp_path / "r.json"
    assert _run(["scan", str(_logs(tmp_path)), "--out", str(out), "--json", str(js)]) == 0
    assert "1 of 2 answers (50%)" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8").startswith("# Cassandra answer check")
    assert json.loads(js.read_text(encoding="utf-8"))["results"][0]["verdict"] == "flagged"


def test_scan_fail_over_gates_ci(tmp_path):
    logs = str(_logs(tmp_path))
    assert _run(["scan", logs, "--out", str(tmp_path / "a.html"), "--fail-over", "60"]) == 0
    assert _run(["scan", logs, "--out", str(tmp_path / "b.html"), "--fail-over", "40"]) == 1


def test_scan_bad_input_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("nope", encoding="utf-8")
    assert _run(["scan", str(bad)]) == 2
    assert "line 1" in capsys.readouterr().err


def test_scan_llm_without_a_key_explains_setup(tmp_path, capsys):
    assert _run(["scan", str(_logs(tmp_path)), "--llm"]) == 2
    assert "OPENAI_API_KEY" in capsys.readouterr().err


async def test_sdk_check_runs_offline_without_a_key():
    r = await cassandra.check("It is 54.", tool_calls=[{"name": "f", "result": {"fee": 45}}])
    assert r.verdict == "flagged" and r.layers == ["value"]


# --- HTTP API ------------------------------------------------------------------

def _client(monkeypatch, key=None):
    from fastapi.testclient import TestClient

    from cassandra.server import create_app

    if key:
        monkeypatch.setenv("CASSANDRA_API_KEY", key)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    reload_settings()

    async def fake(q, a, s):
        return ClaimReport(claims=[Claim(claim="via FedEx", status="contradicted")])
    monkeypatch.setattr(check_mod, "claim_check", fake)
    return TestClient(create_app())


def test_api_check_and_health(monkeypatch):
    c = _client(monkeypatch)
    assert c.get("/health").json()["llm"] is True
    r = c.post("/v1/check", json={"id": "x", "answer": "Ships via FedEx.",
                                  "context": "Carrier: UPS"}).json()
    assert r["verdict"] == "flagged" and r["findings"][0]["kind"] == "contradicted"


def test_api_requires_the_key_when_set(monkeypatch):
    c = _client(monkeypatch, key="s3cret")
    body = {"answer": "ok", "context": "ok"}
    assert c.post("/v1/check", json=body).status_code == 401
    ok = c.post("/v1/check", json=body, headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
