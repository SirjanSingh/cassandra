# Session log: 2026-11-25 — action check + chat-conversation import

Branch: `claude/action-check`, cut from `claude/project-thread-9g4qva` (PR #1). Nothing was
merged, force-pushed, deleted or published.

## Scope

The founder asked for the next move: shortlist ideas, then start one on a new branch.
Constraints tonight: no OpenAI key and no working CI (GitHub billing lock), so the idea had
to be offline and measurable without an LLM.

Shortlist considered:
1. **"Tool errored, bot said done" check** — no spec, no LLM; the Nov 5 probe reported 80%
   precision on tau-bench. **Picked**, with (2) because measuring it needs (2).
2. **Import whole chat conversations** (OpenAI `messages`) so audits take raw exports.
   **Picked.**
3. PII redaction in reports (needed before audits). Next.
4. `cassandra init`: mine a grounding spec from logs. Bigger; after audits show demand.
5. Report every failing rule claim per turn, not only the first. Small.

## What changed and why

- `cassandra_ai/importers.py`: OpenAI-style conversations → one `Turn` per assistant text
  reply. Handles stringified `tool_calls`, JSON-string arguments, content parts, inline
  `<function_calls>` markup, and results matched by `tool_call_id` or in order.
- `scan.load_turns`: rows with `messages` / `traj` / `conversation` are expanded; a
  pretty-printed `.json` list works too (falls back to whole-file JSON only when line 1
  isn't JSON, so the existing "bad line" errors are unchanged).
- `cassandra_ai/actions.py` + engine layer `action` (finding kind
  `claimed_done_after_error`). Runs whenever a turn has tool calls; no spec.
- `poc/taubench/run_action_check.py`: measures it on the 1,980 tau-bench trajectories.

## The finding (the decision, not just the diff)

- The probe's rule, re-run through the shipped importer, reproduced its 80% (36 failed / 9
  passed trajectories). **Reading all 49 flagged answers showed it was not catching lies:**
  nearly every one admits the error. Task failure correlated with tool errors, and the agents
  were honest about them. Only 1 answer clearly claimed a failed action was done.
- So the shipped rule also requires that the answer admits no problem, and uses
  past-participle completion phrases with no hedges. It flags exactly 1 turn: the real one.
- Conclusion for strategy: on strong models this failure is ~1 in 2,000 conversations. Keep
  the check (free, precise) but don't lead with it. EVIDENCE.md now says not to quote 80%.
  This also corrects the consolidated plan doc, which recommended this check on the 80% figure.

## Verification

- `pytest`: 68 passed (57 + 7 action + 4 importer). `ruff` clean, `mypy cassandra_ai scripts`
  clean.
- `cassandra demo`: still 8 of 50. The TravelPal sample has no tool errors with done-claims.
- tau-bench run: 1,980 trajectories → 22,179 turns in ~3 s, no API key.
  `poc/taubench/results.json` holds the summary and the flagged turn.

## Open items

- v1's rules were written after reading the 49 answers; measure on fresh logs before
  quoting precision.
- English-only regexes.
- PII redaction (shortlist #3) before any audit report leaves the building.
