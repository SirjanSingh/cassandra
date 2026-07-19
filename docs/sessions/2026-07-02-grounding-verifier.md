# Session Log: 2026-07-02 — B1 + B2: Grounding Verifier and the oracle swap

Branch: `cassandra-v2`.

## Scope

Implement **B1** from the v2 plan (`~/.claude/plans/cheerful-crunching-stroustrup.md`,
detail in `EVAL_PLAN.md` §6 L1): the pure, deterministic grounding verifier that will
become the primary pass/fail oracle. This was the only roadmap step fully implementable
and testable offline today (B2 depends on it; the selfeval re-run needs live services).

## Why (the decision, not just the diff)

The load-bearing pass/fail verdict is currently an LLM call (temp 0.2, sees no tools) —
the root of the broken 12%==12% baseline-vs-candidate delta (EVAL_PLAN F3). For
structured-tool agents the tool ledger is a closed-world oracle: the failure class can be
*derived by rule* and the verdict can cite the exact tool call. B1 builds that checker as
a standalone module; **nothing is wired into the pipeline yet** — B2 swaps
evaluator/replay/redteam/gate onto it after review.

Key design choices (per plan):
- `GroundingSpec` is the per-agent unit of config (keeps Cassandra agent-agnostic);
  ShopBot's spec is bundled as `SHOPBOT_SPEC`. Rules are declarative/serializable
  (`success_key` string, regex extractors) rather than lambdas.
- The checker **abstains instead of guessing** (`abstain=True`, `failure_class=None`)
  when no extractor fires + no decline marker, or a claim matches no lookup rule — that's
  the L2 (LLM judge) handoff point.
- Claims are checked before decline markers, so "I couldn't find it, but it's typically
  30 days" is still a hallucination.
- Never raises on garbage ledger entries (non-dict entries, non-dict results).

## Changes

- **New** `cassandra/grounding.py` — `LookupRule`, `GroundingSpec`, `GroundingVerdict`,
  `check_grounding()`, bundled `SHOPBOT_SPEC` (refund-window / carrier / eta regex
  extractors, decline markers). Pure: no LLM, no network, no env, no pipeline imports.
- **New** `tests/test_grounding.py` — 11 tests written first (TDD; watched them fail on
  the missing module): hallucination (tool miss + tool-never-called), tool_failure (null
  carrier/eta on a successful lookup), ok (grounded policy, grounded order, honest
  decline), decline-then-fabricate is still hallucination, two abstain paths, garbage
  ledger robustness, and a custom third-party spec.

## Verification

- `pytest tests/test_grounding.py -q` → 11 passed.
- `pytest` → **54 passed** (was 43), 1 pre-existing ADK deprecation warning.
- `ruff check` on both new files → clean.
- `mypy cassandra` → same 12 pre-existing errors in untouched files
  (`state.py`, `phoenix_experiments.py`, `evaluator.py`); `grounding.py` adds none.

## Part 2 (same session): B2 — the oracle swap (EVAL_PLAN.md §6, fixes F3)

The load-bearing pass/fail verdict in Evaluator / TraceReplay / RedTeam / the CI gate was
a prose LLM judge (temp 0.2, never saw tool results) — the root of the broken 12%==12%
baseline-vs-candidate delta. All four now score through one shared oracle.

**Generality decision (user asked "are we just working around ShopBot?"):** the verifier
core is agent-agnostic; only the bundled `SHOPBOT_SPEC` is demo config. Third-party
agents plug in via `GROUNDING_SPEC_FILE` (same pattern as `BASELINE_PROMPT_FILE`), and
two graceful fallbacks keep the zero-config path working: (1) an agent whose `/chat`
reply has **no `tool_calls` key** is never grounded-scored (avoids false hallucination
verdicts on agents that don't report a ledger) — LLM judge takes over; (2) the spec
abstaining also falls back to the judge. A configured-but-broken spec file raises loudly
rather than silently misgrading.

Changes:
- **New** `cassandra/oracle.py` — `Score`, `resolve_spec()` (`GROUNDING_SPEC_FILE` →
  bundled ShopBot spec), `deterministic_verdict()` (None when no ledger / abstain),
  `score_case()` (grounding first, LLM judge fallback; judge prompt moved here from
  evaluator — one source of truth).
- `cassandra/config.py` — new `grounding_spec_file` setting (+ `.env.example` entry).
  **Restart servers after setting it** (`get_settings()` is cached).
- `cassandra/evaluator.py` — `_JUDGE`/`_Score`/`_judge` removed; `_score_one` scores via
  `oracle.score_case` with the reply's `tool_calls`.
- `cassandra/redteam.py` — same swap; `_ask` now returns the full response dict.
- `cassandra/replay.py` — deterministic verdict on the *after* answer's own ledger
  decides `fixed`; the before/after LLM judge remains only as the fallback.
- `cassandra/gate.py` — `_ask_agent` returns the full dict; `_judge_case` delegates to
  `oracle.score_case`; imports moved off `evaluator._JUDGE`.
- Contract docs updated (`tool_calls` is now an optional-but-recommended reply field):
  `cassandra/patient_client.py` docstring, `examples/adapter_template.py`,
  `docs/WORKFLOWS.md` ("Bring your own agent" + config block).
- `tests/test_oracle.py` (10 tests, written first/RED): oracle unit tests (deterministic
  pass/fail with LLM patched to explode, both fallbacks, spec resolution from file) +
  stage integration for evaluator/replay/redteam. `tests/test_gate.py` updated to the new
  mock contract + a new no-LLM deterministic gate test.

Verification (whole session): `pytest` → **66 passed** (43 → 54 after B1 → 66 after B2);
`ruff check .` clean; `mypy` improved 26 → 25 errors (all remaining pre-existing).

## Open items

- **B3** next per the plan: behavior-labeled eval triples + real meta-eval
  (per-class precision/recall/F1 on the production path), demote the Diagnostician's
  judge to abstain-only, judge-vs-oracle CI gate.
- Still pending: re-run `selfeval` on the production path for the true post-F1 accuracy
  (needs the Patient + a model backend running); also worth driving one full
  `scripts/run_pipeline.py` cycle live to watch the recovered baseline-vs-candidate delta.
- Known limits (by design, measured later via L3): regex extractors in `SHOPBOT_SPEC` are
  ShopBot-specific; field claims are checked for *presence of grounding*, not value
  equality; prompt_drift is not detected deterministically (abstain → LLM judge).
- The Synthesizer still emits `expected_answer`, but it is no longer load-bearing when a
  ledger is present (the runtime tool ledger is the oracle).
