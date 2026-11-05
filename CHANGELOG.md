# Changelog

## 0.4.0 (unreleased)

Fixes two defects in 0.3.0's packaging and closes a security hole in the system-prompt
override that Cassandra's replay/eval/red-team/gate use. **0.3.0 should be yanked once 0.4.0
is published** (see "Release steps" below).

### Breaking

- **The import package is now `cassandra_ai`** (was `cassandra`). The `cassandra` import
  name belongs to the Apache Cassandra driver (`cassandra-driver`); installing 0.3.0 next to
  it made one shadow the other. Update `from cassandra.x import …` to `from cassandra_ai.x
  import …` and `python -m cassandra.mcp_server` to `python -m cassandra_ai.mcp_server`. The
  PyPI name (`cassandra-ai`) and the commands (`cassandra`, `cassandra-mcp`,
  `cassandra-gate`) are unchanged.
- **The wheel no longer installs top-level `patient` and `dashboard` packages.** They squatted
  generic import names in users' environments. The ShopBot demo agent and the dashboard now
  run from a source checkout; `cassandra dashboard` says so on a pip install.
- **`system_override` now fails closed.** The demo Patient and `examples/adapter_template.py`
  (the file teams copy into their agents) honor it only when `session_id == "test"` AND
  `REPLAY_SHARED_SECRET` is configured on the agent AND `X-Cassandra-Token` matches it. With no
  secret they used to honor it for anyone, a prompt-replacement hole on any reachable endpoint
  whose traffic Cassandra's Watcher also ignores. **Set `REPLAY_SHARED_SECRET` to the same
  value on Cassandra and the agent, locally too**, or candidate-prompt runs are refused.
- **`google-adk` moved from `[full]` to a new `[adk]` extra.** Only the Agent Engine wrapper
  (`loop_agent.build_adk_agent`, `deploy/agent_engine.py`) uses it, and its
  `opentelemetry-api<=1.44` cap blocked the CVE-2026-114603 fix. `[dev]` includes it.

### Fixed

- `pip install "cassandra-ai[full]"` was broken for fresh installs: `mcp>=1.2.0` resolved to
  mcp 2.x, which removed `mcp.server.fastmcp`, so `cassandra mcp` / `cassandra-mcp` failed to
  import. Pinned to `mcp>=1.2.0,<2`.
- Every runtime dependency now has an upper bound at the next major above the versions the
  test suite passes with; `ruff` and `mypy` are pinned in `[dev]`.
- A fresh `[full]` install now resolves `opentelemetry-api` 1.45.2, which includes the fix for
  CVE-2026-114603 (quadratic-time parsing of the W3C `tracestate` header, reported by
  pip-audit). Not established whether Cassandra's own endpoints reach the vulnerable function.
- Token comparison for `system_override` is constant-time on bytes in both the Patient and the
  adapter template (the template used `!=`; the Patient raised `TypeError` on non-ASCII
  header values).
- `REPLAY_SHARED_SECRET` values are stripped of surrounding whitespace (Secret Manager and
  `echo` add a trailing newline that can't be sent in an HTTP header).
- `__version__` was stuck at 0.1.0; it is now the single version source (hatch dynamic
  version).

### Added

- `override_applied` in the agent `/chat` reply (Patient and adapter template). When an agent
  reports `false` for a request that carried an override, `ask_patient` raises
  `OverrideRejectedError` and `cassandra-gate` exits 2, instead of silently scoring the live
  prompt as if it were the candidate (which could pass a prompt edit that was never run).
  Agents that don't report the field behave as before.
- A one-time warning when Cassandra sends an override with no `REPLAY_SHARED_SECRET`
  configured.
- `scripts/smoke_install.py [--full]`: builds the wheel and checks it in a clean venv (wheel
  contents, co-install with cassandra-driver, offline `scan`, the light/full split, MCP
  import, the opentelemetry fix).
- `tests/test_packaging.py`: wheel contents, entry points, version source, dependency caps.

### Release steps (maintainers)

1. `python scripts/smoke_install.py --full` and `pytest` on a clean checkout.
2. `python -m build` and `twine check dist/*`, then `twine upload dist/*`.
3. On PyPI, yank 0.3.0 with the reason: "installs a top-level `cassandra` package that
   conflicts with cassandra-driver, and `[full]` is broken by mcp 2.x; use >= 0.4.0".

## 0.3.0 (2026-11-05)

- Light default install (`pydantic`, `pydantic-settings`, `python-dotenv`) for the CLI and the
  offline `cassandra scan`; everything else moved to `[full]`.
- `cassandra scan`: offline check of exported chat logs with the deterministic grounding rule.
