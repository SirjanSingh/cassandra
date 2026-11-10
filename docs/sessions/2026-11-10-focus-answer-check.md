# Session Log: 2026-11-10 — focus branch: Cassandra becomes one product

Branch: **`focus/answer-check`** (cut from `feature/nli-and-hindi` @ ce5d0e7, which keeps the
full old pipeline untouched).

## Scope

The user asked to move what we're keeping to a new branch, cut brutally, add what's
sellable, fix architecture and business model, and document how we proceed.

## Decisions (the why)

- **One product:** *check a bot's answers against the data it was given.* Chosen because
  it's the only thing with measured evidence. The claim-by-claim check caught 43% on
  RAGTruth vs 9% for the whole-answer judge.
- **Cut:**
  - The 9-stage Phoenix pipeline, MCP server, dashboard and web UI
  - ShopBot, deploy and GCP code
  - The whole-answer judge, jury and NLI layer
  - Gate and PR automation, and ~20 planning docs
  Reasons are in `docs/STRATEGY.md §2`. Nothing ran on a real customer, and the
  Phoenix dependency blocks adoption.
- **Business model:** open core plus done-for-you.
  - Free OSS → **Answer Audit** ($750 / ₹50k per bot; first 3 free) → **Guard** (from
    $400 / ₹30k per bot per month).
  - Audits first, because they need nothing unbuilt and produce real-data labels.
- **Plan with gates** (`docs/ROADMAP.md`):
  - Gate A (Dec 8): 2 of 3 free audits confirm real problems.
  - Gate B (Jan 19): first paid audit plus a Guard pilot.
  - Fallback: an agent action firewall.

## What changed

**New / rewritten package (v0.4.0):**
- `models.py`: `Turn` (with `context` for RAG docs), `Finding`, `TurnResult`, `Report`.
- `engine.py`: three layers (rule → value → claim). Verdicts are flagged / ok / declined /
  unchecked; "unchecked" is never "ok".
- `llm.py`: OpenAI SDK against any OpenAI-compatible base URL (OpenAI, OpenRouter, Azure,
  local Ollama). The request shape is unchanged from the benchmark. `openai` is optional.
- `config.py`: real env vars now beat `.env`. This fixes the `load_dotenv(override=True)`
  gotcha. Settings: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `CASSANDRA_MODEL` (or
  `OPENAI_MODEL`), `CASSANDRA_CONCURRENCY`, `CASSANDRA_API_KEY`, `CASSANDRA_SPEC_FILE`.
- `report.py`: self-contained HTML (escaped, no scripts, dark mode), Markdown, JSON.
- `server.py`: `cassandra serve`, with `POST /v1/check`, `/health` and an optional bearer key.
- `cli.py`: `demo` (bundled TravelPal sample), `scan` (`--llm`, `--spec`, `--json`,
  `--fail-over` for CI), `serve`.
- `__init__.py`: SDK `await cassandra.check(answer, question=, tool_calls=, context=)`.
- `grounding.py`: unchanged logic. The ShopBot spec moved into the tests; `load_spec()` added.

**`value_check` fixes** (it raised false alarms on the TravelPal sample):
- source dates like `2016-06-24` are now read as numbers
- rounded source numbers are accepted (0.83064 → 0.8306)
- numbers echoed from the user's question are accepted

On RAGTruth test, `value_check` went from 8 caught / 16 false alarms to 6 / 14.
`claim_check` is unchanged at 38 / 121.

**Packaging:** the core is pydantic + pydantic-settings only. Extras: `[llm]`, `[serve]`,
`[full]`, `[dev]`. The console scripts `cassandra-mcp` and `cassandra-gate` are gone.

**Docs:** new `README.md`, `docs/STRATEGY.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
`EVIDENCE.md` and `OUTREACH.md`, plus `CLAUDE.md`. The old docs are deleted from this branch
(they remain on `feature/nli-and-hindi`).

**Examples:** `examples/logs.jsonl`, `spec.json`, `check_live.py`.

**POC folders:**
- `poc/ragtruth/run_claims.py` is now self-contained. `run_judge.py` was removed; its
  saved results are kept as the baseline.
- `poc/travelpal`: the scripts that used the old pipeline were removed; data, labels and
  the bot remain.

## Verification

- `pytest`: 43 passed. `ruff`: clean. `mypy cassandra`: clean.
- `cassandra demo` offline: 8 of 50 flagged, all 8 hand-labelled bad, 0 false alarms
  (15 labelled bad).
- `cassandra demo --llm` / `scan --llm` (live gpt-4o-mini): 10 flagged; 8 bad, 2 false
  alarms. That's no extra recall on TravelPal: its remaining errors are wrong-entity /
  wrong-date lookups, which no answer-vs-data check can see. Documented in EVIDENCE.md.
- `examples/logs.jsonl` offline: 3 of 4 flagged as intended.
- **Release check:**
  - `python -m build`: wheel + sdist; `twine check` PASSED.
  - The wheel holds only `cassandra/` and the samples.
  - In a fresh venv the core install is 9 packages, and `cassandra demo` works (8 of 50).
  - `scan --llm` without `[llm]`, and `serve` without `[serve]`, print one-line install hints.
- HTML report viewed in a browser: renders cleanly. With `--llm` the top flags include
  nitpicks ("based on the latest exchange rate"), the false-alarm problem Phase 1 targets.
  That's why `cassandra demo` defaults to offline (8 flags, all real).

## Open items

- **Rule layer: check field *values*, not just presence.** For example "FedEx" when
  `carrier` = "UPS" is only caught by the LLM layer today. Cheap; would make the offline
  demo stronger.
- **Roadmap Phase 1:** a second-pass verification to cut false alarms (target at least 50%
  of flags real, recall at least 35%).
- **PyPI 0.4.0:** the user uploads after merging to main. PyPI's 0.3.0 is still the old
  product.
- `AGENTS.md` (untracked, not ours) was left alone.
