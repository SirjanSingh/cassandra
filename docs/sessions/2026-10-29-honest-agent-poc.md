# Session Log: 2026-10-29 — positioning reset + honest real-agent proof of concept

Branch: `feature/nli-and-hindi` (uncommitted).

## Scope

1. The user felt the product had sprawled. We agreed on a one-line definition: *Cassandra catches
   when an agent states a fact its tools never gave it, and turns each one into a tested prompt
   fix plus a regression test.* Buyer: B2B. Delivery: open-core, self-hosted first. Price per
   supervised agent. Integration in 3 levels (read-only traces → replay endpoint → CI gate/PR).
   These were discussed in chat only; no positioning doc was written.
2. Built a proof of concept on an **unrigged** agent to see whether Cassandra works off the demo.

## Changes

- **New** `poc/travelpal/`:
  - `agent.py`: gpt-4o-mini agent, normal prompt, real APIs (Frankfurter, Open-Meteo); speaks
    the `patient_client` contract.
  - `questions.json`: 98 realistic questions in 7 categories.
  - `collect.py`: runs them via `ask_patient` → `runs.jsonl`.
  - `labels.json`: hand labels, written before scoring.
  - `grounding_spec.json`: per-agent spec.
  - `score.py`: rule / LLM judge / cascade vs labels → `results.json`.
  - `README.md`: results.
- No changes to `cassandra/`.

## Results (see poc/travelpal/README.md)

- Agent was wrong on 14/98 turns:
  - 9 answered from memory with no tool behind them
  - 3 wrong geocoded place
  - 2 misreported tool data
- **0/25 "tool failed → improvised"** — the ShopBot failure mode didn't occur with a normal prompt.
- Cascade: precision 82%, recall 64%.
  - Caught 9/9 answered-from-memory, 0/5 wrong-place/misreported.
- Rule alone: precision 88%. LLM judge alone: precision 37% (19 false alarms).

## Verification

- Live run against real APIs and the OpenAI API.
- `ruff check poc/` clean.
- `pytest` not affected (no package code changed).

## Open items

- **Bug:** `Diagnostician.judge` isn't given today's date, so it calls correct current dates
  "fabricated" (q016, q053). One-line fix in the judge prompt.
- **Judge over-flags honest declines** as `tool_failure`. The `_SYSTEM` prompt needs a rule:
  "an accurate statement that data is unavailable is OK."
- **Grounding rule gap:** it checks only that *a* successful call exists. Next detector:
  - entity/argument checks (claimed place vs `result.place`)
  - ignore amounts echoed from the user's input (q081 false positive)
- Prove the fix loop on TravelPal: Patcher on the answered-from-memory class → rerun the 98 →
  measure. Use a held-out question set to avoid tuning on the test set.
