# Session Log: 2026-10-29 — positioning reset + honest real-agent proof of concept

Branch: `feature/nli-and-hindi`.

## Scope

1. The user felt the product had sprawled. We agreed on a one-line definition: *Cassandra catches
   when an agent states a fact its tools never gave it, and turns each one into a tested prompt
   fix plus a regression test.* Buyer: B2B. Delivery: open-core, self-hosted first. Price per
   supervised agent. Integration in 3 levels (read-only traces → replay endpoint → CI gate/PR).
   Written up later the same day in `docs/POSITIONING.md`.
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

---

## Week 1 (same day): judge fix, held-out set, real fix loop

### Changes

- **`cassandra/diagnostician.py`**:
  - the judge prompt now starts with `TODAY'S DATE`, and `_SYSTEM` says to judge dates against it;
  - a plain "couldn't retrieve" counts as surfacing a failure;
  - added an honest-decline example.
  - **Why:** the PoC showed the judge calling correct 2026 dates "fabricated" and flagging honest declines (19 false alarms in 98).
- `poc/travelpal/`:
  - `questions_heldout.json`: 50 new questions, written before running; grounding spec frozen.
  - `fix_loop.py`: the real Diagnostician → RootCauseAnalyst → Patcher chain on q090, with Phoenix stubbed.
  - `collect.py`: new `--questions`, `--out` and `--system-file` (system_override) options.
  - `score.py`: new `--runs`, `--labels` and `--out` options.
  - New run, label and result files for the candidate and held-out sets.
- **New** `docs/POSITIONING.md`: one-page what, who, why-us and pricing hypotheses.

### Results

- **Judge alone:** precision 37% → 53%. The cascade on the original set went 82% → 75% because of one judge-noise false alarm.
- **Held-out detection** (frozen spec, the fair number): cascade precision 100% (11/11), recall 73%.
- **Fix loop.**
  - The patch was narrow ("visa costs"), but it included a general "if tool data is missing, say so" line.
  - Held-out bad answers: **15/50 → 3/50**. Original set: 14/98 → 8/98.
  - 63/63 answerable questions were still answered.
  - Answered-from-memory errors fell 20 → 4. Wrong place/date barely moved (9 → 7).

### Verification

- `pytest`: 101 passed.
- `ruff` clean on `cassandra/diagnostician.py` and `poc/`.
- All runs are live against the real APIs; every run set was hand-labelled before scoring.

### Open items (new)

- The Patcher sees one incident, so the patch wording is narrow. Patch from a **cluster** of similar incidents.
- The Synthesizer, Evaluator, Replay and RedTeam stages were not exercised here. The test sets were mine, not synthesized, and Phoenix was stubbed.
- Wrong-place and wrong-date failures are invisible to Cassandra and unfixable by prompt. They need entity/argument checks.
- Week 2 is next: `cassandra scan logs.jsonl` (see `docs/30_DAY_PLAN.md`).
