# Session Log: 2026-11-05 — light install + PyPI-ready 0.3.0

Branch: `feature/nli-and-hindi`.

## Why

- `cassandra-ai` was never on PyPI (pypi.org returned 404), even though the README said it was.
- The only working install was a long `pip install "git+https://…@feature/nli-and-hindi"`.
- That install pulled the *whole* stack (Google ADK and GenAI, Cloud Firestore and Secret Manager, OpenAI, MCP, OpenTelemetry, FastAPI/uvicorn) just to run `cassandra scan`, which needs only Pydantic.
- That's the wrong first experience for outreach (`docs/OUTREACH.md`).

## Changes

- **`pyproject.toml`**:
  - The core `dependencies` are now just `pydantic`, `pydantic-settings` and `python-dotenv`: enough for the CLI and a rule-only `scan`.
  - Everything else moved to a new **`full`** extra; `dev` pulls `cassandra-ai[full]` plus the test tools.
  - Version bumped 0.2.0 → **0.3.0**, because the default install changed.
- **`cassandra/cli.py`**:
  - `main()` wraps a new `_main()`. A `ModuleNotFoundError` for a third-party package prints `pip install "cassandra-ai[full]"` and exits 1.
  - Missing *internal* modules (`cassandra`/`patient`/`dashboard`) still raise, so real bugs aren't hidden.
  - Fixed the `gate` column alignment in the command list.
- **Full install required**, updated in: `deploy/cloudrun.Dockerfile` (`pip install ".[full]"`), `examples/github-actions-prompt-gate.yml` (`cassandra-ai[full]`; it also had the wrong distribution name, `cassandra`), `docs/WORKFLOWS.md`, README (MCP section), and `docs/TESTING_GUIDE.md` (dropped the stale 0.2.0 wheel instructions).
  - `deploy/agent_engine.py` has its own explicit requirements list and is unaffected.
- **Install docs** (`README.md` Quickstart, `docs/SCAN.md`, `docs/OUTREACH.md`): `pip install cassandra-ai` (light) and `pip install "cassandra-ai[full]"` (everything).
- **Tests**: two new CLI tests in `tests/test_scan.py`. One checks a light install gets the `[full]` hint; the other checks that internal import errors are not masked.

## Verification

- `pytest`: 116 passed. `ruff` and `mypy` are clean on `cli.py`.
- `python -m build` → `cassandra_ai-0.3.0` wheel and sdist; `twine check` PASSED on both.
  - The wheel holds only `cassandra/`, `patient/`, `dashboard/` and metadata.
  - The sdist's only env file is `.env.example`, with placeholders only.
- **Fresh venv, light wheel:**
  - The install took 12 s and pulled 7 packages plus `cassandra-ai`.
  - `cassandra` shows the banner. `cassandra scan` on `poc/travelpal/runs_heldout.jsonl` gave the same result as before (8 of 50, 9 not checkable).
  - `scan --judge`, `run`, `dashboard`, `gate` and `mcp` each print the `[full]` hint and exit 1.
- Not verified: a fresh `pip install ".[full]"` and the Cloud Run image build. Extras resolution is standard, but it wasn't run here.

## Open items

- ~~Upload to PyPI~~ **Done.** The user uploaded `cassandra-ai` 0.3.0 with their own token. The first try got a 403 (the token wasn't entered correctly); the retry used `TWINE_USERNAME`/`TWINE_PASSWORD`. Verified from PyPI itself in a fresh venv: the install took 11 s, `cassandra scan` gives 8 of 50, and `cassandra run` prints the `[full]` hint. Pushed after that.
- `cassandra pr <unknown-id>` shows a raw `FileNotFoundError` traceback. Pre-existing and cosmetic.
- The README still says "v0.1 is dev-audience" in the Quickstart. Stale wording.
