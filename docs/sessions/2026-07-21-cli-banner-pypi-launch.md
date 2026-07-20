# Session Log: 2026-07-21 — v0.1 public launch (`cassandra` CLI + banner + PyPI)

Branch: `cassandra-v2`. **STATUS: IN PROGRESS** — resumable; see checklist below.

Plan: `~/.claude/plans/i-want-to-make-piped-flute.md` (Cassandra v0.1 public launch —
`cassandra` CLI + banner + PyPI `cassandra-ai`). Written 2026-07-20, executed this session.

## Goal

Make Cassandra pip-installable (`pip install cassandra-ai`) with a `cassandra` console-script
that prints an ASCII banner and dispatches subcommands (dashboard / run / gate / mcp). Minimal
dev-audience v0.1 — installers still need an LLM key, Phoenix, Node/npx, and an agent to
supervise (documented as prereqs). Import package stays `cassandra`; PyPI name `cassandra-ai`
(fallback `cassandra-supervisor`).

## Execution checklist (update as each lands)

- [x] 1. `cassandra/banner.py` — ASCII art, `get_version()`, `print_banner()`. NOTE fixes:
      (a) hand-drawn art was malformed (read "cassanlra") → regenerated with figlet 'standard'
      font (pyfiglet installed dev-time ONLY to generate; NOT a runtime dep), now reads
      CASSANDRA correctly; (b) `file=None` default resolved at call time (import-time
      `sys.stdout` bypassed capsys); (c) tagline separator ASCII `--` not `·` (cp1252 console
      would UnicodeEncodeError).
      **⚠ `dist/*` is STALE — built before the art fix. MUST `python -m build` again before upload.**
- [x] 2. `cassandra/run_once.py` — runner moved in; `scripts/run_pipeline.py` now a thin wrapper.
- [x] 3. `cassandra/cli.py` — argparse, lazy per-subcommand imports; `mcp` emits zero stdout.
- [x] 4. `pyproject.toml` — name=`cassandra-ai`, version 0.2.0, keywords/classifiers,
      `[project.urls]` (github.com/SirjanSingh/cassandra), `cassandra` script, `python-dotenv` dep.
- [x] 5. Docs — README `## Quickstart (pip)` (prereqs + command table), CLAUDE.md Commands
      block (+ CLI note), `docs/DISTRIBUTION.md` publish flow (PowerShell twine + TestPyPI).
- [x] 6. `tests/test_cli.py` — 7 tests, all pass.
- [x] 7. Verify: `pytest` **73 passed** (66→73); `ruff` clean; `mypy cassandra` exit 0, 10
      pre-existing errors in evaluator/state/phoenix_experiments, **zero in new files**;
      `cassandra` banner renders + resolves v0.2.0 after `pip install -e`. Fixed em-dash in
      argparse description → ASCII (cp1252 console). `python -m build` OK →
      `cassandra_ai-0.2.0-{py3-none-any.whl,.tar.gz}`; wheel contains cli/banner/run_once +
      `dashboard/ui/*.html`, excludes `scripts/`+`web/`; entry points cassandra/-gate/-mcp
      correct; `twine check` PASSED both.
- [x] 7b. **Security audit (pre-publish)** — no secret leaks (local `.env` with real keys
      confirmed NOT in sdist), no eval/exec/pickle/shell=True, no hardcoded creds. Fixed:
      **(#1)** sdist over-inclusion — added `[tool.hatch.build.targets.sdist]` allowlist;
      sdist **17MB → 90KB**, no longer ships `.claude/`/`.vscode/mcp.json`/`web/node_modules/`/
      `EVAL_PLAN.md`/`PRODUCT_PLAN.md`/`tests/`/`deploy/`. **(#2)** timing-safe secret compare
      in `patient/agent.py:resolve_override` (`hmac.compare_digest`). Banner also corrected to
      mixed-case "Cassandra" (cap C only). Deferred-by-design (would break local demo/tests,
      documented instead): #3 `system_override` fails open when `REPLAY_SHARED_SECRET` unset;
      #4 dashboard `/ask`+`/selfeval` unauthenticated (denial-of-wallet on public deploy).
      Re-verified: 73 passed, ruff clean, `twine check` PASSED, wheel+sdist rebuilt.
      PyPI name `cassandra-ai` confirmed AVAILABLE (pypi.org JSON 404).
- [ ] 8. Publish — **NOT STARTED, gated on Sirjan.** `dist/` artifacts built and checked. Next:
      verify `cassandra-ai` free on pypi.org → `twine upload --repository testpypi dist/*` →
      test-install → **PAUSE for Sirjan's explicit OK** → `twine upload dist/*` (irreversible).
      Tokens via `$env:TWINE_USERNAME=__token__` / `$env:TWINE_PASSWORD` — never echoed/committed.

## Reality notes (verified against current tree before starting)

- `dist/` already in `.gitignore` (line 18). No change needed.
- `cassandra/gate.py:main(argv: list[str] | None)` — CLI passes remaining argv through.
- `cassandra/mcp_server.py:main()` — no args; CLI must emit ZERO stdout for `mcp` (stdio JSON-RPC).
- `config.py` has `dashboard_port: int = 8085` but NO `dashboard_host` — CLI defaults `--host` to
  `127.0.0.1`.
- `dashboard/ui/` has `index.html` + `how-it-works.html` — must land in the wheel.

## Verification (final)

`pytest` 73 passed · `ruff check` clean · `mypy cassandra` exit 0 (10 pre-existing, none new) ·
`cassandra` console script prints banner + v0.2.0 · `python -m build` + `twine check` PASSED ·
wheel contents confirmed correct.

## Files touched

- New: `cassandra/banner.py`, `cassandra/run_once.py`, `cassandra/cli.py`, `tests/test_cli.py`,
  this session note.
- Edited: `scripts/run_pipeline.py` (→ thin wrapper), `pyproject.toml`, `README.md`, `CLAUDE.md`,
  `docs/DISTRIBUTION.md`.

## Open items / how to resume

- **Publish (step 8)** is the only remaining task — see checklist. Gated on Sirjan's explicit OK
  for the real PyPI upload (irreversible). `dist/` already built & twine-checked.
- Work is **uncommitted** — not committed yet (no commit was requested). `/wrap` or a manual
  commit will group these. Author as Sirjan, no AI trailer.
- v0.1 caveat: generic top-level `patient`/`dashboard` modules in site-packages; rename deferred.
