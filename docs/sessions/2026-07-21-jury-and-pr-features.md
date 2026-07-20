# Session Log: 2026-07-21 — Multi-judge jury + "open the fix as a PR"

Branch: `multi-agent-v1` (fast-forwarded up to `cassandra-v2` @ `62790b4` at the start of
the session so it carries the eval re-architecture — oracle/grounding — and the CLI, both
of which these two features build on directly).

## Scope

Two enterprise-facing features from the feature roadmap discussion:

1. **Multi-judge jury** — turn the single LLM-as-judge into a *panel* of K inferences
   aggregated by majority vote, with juror **agreement** as a calibrated confidence signal
   and **dissent** surfaced instead of discarded (EVAL_PLAN.md L2 upgrade).
2. **Open the fix as a PR** — a completed supervision cycle can be shipped as a GitHub pull
   request (branch → write the patched prompt → commit → push → `gh pr create`), with the
   postmortem as the body. Cassandra becomes a teammate that opens the fix for review.

## Why (the decisions, not just the diff)

- **Jury answers "how do you know the judge is right?" better than a single call.** The
  deterministic grounding oracle (v2 B1/B2) is still PRIMARY; the jury only upgrades the L2
  *fallback* (no ledger / spec abstains). Agreement calibrates confidence: a 3-0 panel is
  trusted more than a 2-1 split, and confidence is scaled *down* by disagreement. This is
  also the "multi-agent inference from multiple calls" the owner asked for — diversity comes
  from a deterministic temperature spread (juror 0 is always the temp-0 anchor).
- **Opt-in, zero behaviour change at the default.** `JURY_SIZE=1` (default) is the exact
  original single-judge path (report is `None`), so all pre-existing tests and the
  deterministic-supervision guarantee are untouched. `>1` convenes the panel. Costs
  `JURY_SIZE` LLM calls per judged turn/case — documented as "raise deliberately."
- **The PR feature is deliberately NOT wired into the autonomous pipeline.** Editing a prompt
  and opening a PR is outward-facing and hard to reverse, so it is invoked *only* explicitly
  (`cassandra pr <id>`), and even then the local git mutation (branch+commit) and the outward
  push/`gh pr create` are separate gates (`--dry-run` touches nothing; `--push` is the only
  path that talks to GitHub). This matches the human-in-the-loop posture enterprises require.
- **Careful with the existing CLI + MCP (owner's note).** Nothing existing was changed — the
  PR feature is *added* as a new `cassandra pr` subcommand and two *new* MCP tools
  (`diagnose_jury`, `prepare_fix_pr`); `prepare_fix_pr` returns a DRAFT only (no push), so an
  agent never opens a PR on its own.

## Changes

- **New** `cassandra/jury.py` — pure `temperatures_for`, `_tally`, `aggregate_verdicts`
  (majority vote + agreement-scaled confidence + dissent), `aggregate_bools` (strict
  majority; even split fails closed), and async `deliberate()` fan-out (drops erroring
  jurors). Imports only `models` (never `oracle`) to avoid a cycle.
- **New** `cassandra/pr.py` — `PRContent`/`PRResult`, `load_incident()` (reads
  `reports/<id>.json`), pure `build_pr_content()` (title/branch/body from the incident +
  postmortem), and `open_pr()` (git/gh subprocess, `dry_run`/`push` gated).
- `cassandra/models.py` — new `JuryReport` model + `Incident.jury` field. (Left `Verdict`
  untouched — it is an LLM response schema; adding fields would make the model try to fill
  them.)
- `cassandra/config.py` + `.env.example` — `jury_size` (default 1), `jury_max_temperature`.
- `cassandra/diagnostician.py` — `judge()` gained a `temperature` kwarg (default 0.0, so
  behaviour is identical); new `judge_panel()`; `diagnose()` uses the panel per `jury_size`
  and stores the `JuryReport` on the incident + in the SSE event payload.
- `cassandra/oracle.py` — extracted `_judge_once`; new `_judge_fallback` runs a jury when
  `jury_size > 1` (else the single judge). The deterministic-grounding PRIMARY path is
  unchanged.
- `cassandra/report.py` — postmortem now prints a **Jury** line (size, agreement, votes).
- `cassandra/loop_agent.py` — `_write_postmortem` now also dumps `reports/<id>.json` (the
  full serialized `Incident`) so `cassandra pr` can reconstruct the cycle out-of-band.
- `cassandra/cli.py` — new `pr` subcommand (`--prompt-file/--base/--branch/--dry-run/--push`).
- `cassandra/mcp_server.py` — new `diagnose_jury` and `prepare_fix_pr` tools (+ docstring).

## Verification

- `pytest` → **91 passed** (was 66; +18 in `tests/test_jury.py` + `tests/test_pr.py`, and
  the rest of the suite still green — the jury/PR additions are behaviour-preserving at
  defaults).
- `ruff check` on all changed/new files → clean.
- CLI smoke test: `cassandra` lists `pr`; `cassandra pr <id> --dry-run` renders the correct
  title/branch/body from a serialized incident with no git side effects.

## Open items

- End-to-end `--push` path (real branch + `gh pr create`) is untested offline by design;
  exercise it once against a scratch repo/branch before relying on it in a demo.
- The demo ShopBot prompt is a Python constant (`patient/agent.py`), not a file, so the PR
  feature's file-commit path needs `BASELINE_PROMPT_FILE` (a real third-party agent) or
  `--prompt-file`. Worth a follow-up: a demo prompt file so `cassandra pr --push` is
  showable on ShopBot itself.
- Consider surfacing jury agreement in the React cockpit (the SSE payload already carries
  `jury_size` / `jury_agreement`).
- Not yet run live: a full `cassandra run` cycle with `JURY_SIZE=3` against the Patient to
  watch the panel + dissent on real Gemini calls (needs the Patient + a model backend up).
