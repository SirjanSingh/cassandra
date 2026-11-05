# Session Log: 2026-06-29 — Fix F1 (telemetry oracle) + v2 research/planning docs

Branch: `cassandra-v2` (renamed from `research/alternatives-and-market`). `main` is frozen
until hackathon results land.

## Scope

Two things this session:
1. **Research/planning docs** (no code): market/competition + hackathon-dependency alternatives,
   a plain-language project explainer, a learning-resources guide, and a v2 plan.
2. **First code change of v2: the F1 fix** (the production tool-ledger oracle, `EVAL_PLAN.md`
   "L0"). This is the prerequisite for the whole eval re-architecture.

## Why (the decision, not just the diff)

The project's headline "100% diagnostic accuracy" measured the **self-eval HTTP path**, not
production. In production the Diagnostician judged turns with **no tool results** because
`normalize_span` read a top-level `tool_calls` key that never existed, while the Patient emits
the ledger as a JSON string under `attributes["tool.calls"]`. That made the "how do you know
the judge is correct?" credibility story rest on a signal the judge never actually received.
Fixing this first reveals the *real* accuracy and unblocks B1+ (deterministic verifier).

Product decisions recorded this session: telemetry backend → **Langfuse** (Phoenix kept as
adapter); model layer → **LiteLLM**. (Recommendations for the still-open decisions live in
`docs/PROJECT_EXPLAINER.md` §7.)

## Changes

- `cassandra/phoenix_mcp.py` — new pure helper `_extract_tool_calls(attrs)` (handles the
  Patient's JSON-string `tool.calls`, already-parsed lists, nested OpenInference `tool.calls`,
  and `llm.tool_calls`; never raises). `normalize_span` now uses it instead of the dead
  `raw.get("tool_calls", [])`.
- `cassandra/diagnostician.py` — `diagnose()` now passes `span.tool_calls` directly (dropped
  the broken `or span.raw.get("tool.calls")` top-level fallback). `judge()` signature unchanged
  (shared by pipeline / self-eval / MCP — one source of truth).
- `tests/test_phoenix_mcp_helpers.py` — 3 new tests: JSON-string ledger, already-list ledger,
  and `_extract_tool_calls` robustness (OpenInference shapes + garbage → `[]`).
- `tests/test_diagnostician.py` — `test_production_path_feeds_tool_ledger_to_judge`: drives a
  realistic span through `normalize_span → diagnose`, captures the judge prompt, asserts the
  tool ledger is present (the test whose absence let F1 hide).
- Docs honesty pass: `docs/SYSTEM_DESIGN.md` §9 (determinism caveat), §10 (new F1 row), §11
  status line now flag that the 100% was self-eval-path-only and say to re-run `selfeval`.
- New v2 docs: `docs/MARKET_AND_ALTERNATIVES.md`, `docs/PROJECT_EXPLAINER.md`,
  `docs/LEARNING_RESOURCES.md`; plan at `~/.claude/plans/cheerful-crunching-stroustrup.md`.

## Verification

- `pytest tests/test_phoenix_mcp_helpers.py tests/test_diagnostician.py -v` → 10 passed
  (incl. 4 new F1 regression tests).
- `pytest` → **43 passed**, 1 pre-existing ADK deprecation warning.
- `ruff check` on changed files → clean.
- `mypy cassandra` → 12 errors, **all pre-existing** in untouched files (`state.py`,
  `phoenix_experiments.py`, `evaluator.py`); the changed files add none.

## Open items

- **Re-run `selfeval` on the production path** to record the true post-fix accuracy (needs the
  Patient + a model backend running; not done offline this session).
- Next per the plan: **B1** deterministic Grounding Verifier (`cassandra/grounding.py` +
  `GroundingSpec`), then B2 swap evaluator/replay/redteam/gate onto it.
- Plan file: `~/.claude/plans/cheerful-crunching-stroustrup.md` (Part A done; Part B roadmap).
</content>
