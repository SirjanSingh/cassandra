"""`cassandra` CLI + banner: offline tests (subprocess/heavy deps mocked)."""

import importlib.metadata

import pytest

import cassandra_ai.banner as banner
import cassandra_ai.cli as cli


# --- banner ---------------------------------------------------------------

def test_banner_contains_art_and_version(capsys):
    banner.print_banner()
    out = capsys.readouterr().out
    assert "Cassandra" in out or "___" in out  # ASCII art present
    assert f"v{banner.get_version()}" in out


def test_get_version_fallback_when_not_installed(monkeypatch):
    def boom(_name):
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(banner, "version", boom)
    assert banner.get_version() == "0.0.0-dev"


# --- dispatch -------------------------------------------------------------

def test_no_args_prints_banner_and_help(capsys):
    cli.main([])  # must not raise
    out = capsys.readouterr().out
    assert "commands:" in out
    assert "dashboard" in out and "mcp" in out


def test_dashboard_dispatch(monkeypatch, capsys):
    called = {}

    def fake_run(app, host, port):
        called["app"] = app
        called["host"] = host
        called["port"] = port

    monkeypatch.setattr("uvicorn.run", fake_run)
    cli.main(["dashboard", "--port", "9999"])
    assert called["app"] == "dashboard.main:app"
    assert called["port"] == 9999
    assert "Cassandra" in capsys.readouterr().out or called["host"] == "127.0.0.1"


def test_dashboard_is_found_in_a_source_checkout():
    assert cli._dashboard_available()  # the test suite runs from the repo


def test_dashboard_outside_a_checkout_explains_instead_of_crashing(monkeypatch, capsys):
    # The wheel ships only `cassandra_ai`, so a pip install has no `dashboard` package;
    # say how to get it rather than letting uvicorn fail on an import string.
    monkeypatch.setattr(cli, "_dashboard_available", lambda: False)
    monkeypatch.setattr("uvicorn.run", lambda *a, **k: pytest.fail("must not start uvicorn"))
    with pytest.raises(SystemExit) as e:
        cli.main(["dashboard"])
    assert e.value.code == 1
    assert "source checkout" in capsys.readouterr().err


def test_run_dispatch(monkeypatch, capsys):
    called = {"n": 0}
    monkeypatch.setattr("cassandra_ai.run_once.main", lambda: called.__setitem__("n", 1))
    cli.main(["run"])
    assert called["n"] == 1
    assert capsys.readouterr().out  # banner printed


def test_gate_passthrough(monkeypatch):
    seen = {}
    monkeypatch.setattr("cassandra_ai.gate.main", lambda argv: seen.__setitem__("argv", argv))
    cli.main(["gate", "--prompt", "P.txt", "--threshold", "0.9"])
    assert seen["argv"] == ["--prompt", "P.txt", "--threshold", "0.9"]


def test_mcp_emits_nothing_on_stdout(monkeypatch, capsys):
    monkeypatch.setattr("cassandra_ai.mcp_server.main", lambda: None)
    cli.main(["mcp"])
    assert capsys.readouterr().out == ""  # stdio JSON-RPC: banner would corrupt the protocol
