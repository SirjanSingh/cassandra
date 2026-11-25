# Changelog

## 0.4.0 (unreleased)

0.4.0 is a different product from 0.3.0: Cassandra now does one job, checking a bot's
answers against the data the bot was given (see `docs/STRATEGY.md`). The Phoenix
supervision pipeline, MCP server, dashboard and CI prompt gate are gone; they remain on the
`feature/nli-and-hindi` branch. **0.3.0 should be yanked once 0.4.0 is published.**

### Breaking

- **The import package is `cassandra_ai`** (was `cassandra`). `cassandra` is the import name
  of the Apache Cassandra driver (`cassandra-driver`); 0.3.0 installed a top-level
  `cassandra` package that shadowed it. The PyPI name (`cassandra-ai`) and the `cassandra`
  command are unchanged. Use `import cassandra_ai` / `await cassandra_ai.check(...)`.
- The wheel ships only `cassandra_ai/` (0.3.0 also installed top-level `patient` and
  `dashboard` packages).
- Commands: `cassandra demo`, `cassandra scan`, `cassandra serve`. `run`, `dashboard`,
  `gate`, `mcp` and the `cassandra-mcp` / `cassandra-gate` scripts are removed.
- Extras: `[llm]` (claim check), `[serve]` (HTTP API), `[full]` = both. The core install is
  pydantic + pydantic-settings only.

### Added

- Three-layer check engine (tool-call rule, numbers and times, claim by claim), Python SDK,
  `POST /v1/check` HTTP API, and HTML / Markdown / JSON reports.
- The tool-call rule compares stated field values with the returned ones: "FedEx" when the
  order lookup returned UPS is flagged `contradicted`. It flags only when every successful
  result is comparable and disagrees; per-rule opt-out `match_values: false`. Every match of
  a claim extractor is checked, not only the first.
- CI (GitHub Actions): ruff, mypy, pytest and a clean-venv smoke install on Linux, macOS
  and Windows, plus build and `twine check --strict`.
- `scripts/smoke_install.py [--full]` and `tests/test_packaging.py`.

### Fixed

- Every dependency has an upper bound at the next major (0.3.0's floor-only `mcp>=1.2.0`
  resolved to mcp 2.x and broke `[full]`). `ruff` and `mypy` are pinned in `[dev]`, and the
  ruff rule set is pinned, so "lint clean" no longer depends on the installed ruff.
- One version source: hatch reads `__version__` from `cassandra_ai/__init__.py`.
- Real environment variables now beat `.env` (0.3.0 loaded `.env` with override).

### Release steps (maintainers)

1. CI green on the release commit (or locally: `pytest`, `ruff check .`,
   `mypy cassandra_ai scripts`, `python scripts/smoke_install.py --full`).
2. `python -m build`, then `twine check --strict dist/*`, then `twine upload dist/*`.
3. Verify from PyPI in a fresh venv: `pip install cassandra-ai`, then `cassandra demo`
   (expect 8 of 50 flagged).
4. On PyPI, yank 0.3.0 with the reason: "installs a top-level `cassandra` package that
   conflicts with cassandra-driver, and `[full]` is broken by mcp 2.x; use >= 0.4.0".

## 0.3.0 (2026-11-05)

- Light default install for the CLI and the offline `cassandra scan`; everything else in
  `[full]`. Last release of the Phoenix supervision pipeline.
