# Session Log: 2026-07-02 — RL merge proposal (Cassandra × ZombieE)

Branch: `cassandra-v2`. **No application code touched** — this session was product strategy +
one new doc. Recorded per the session protocol because a durable, reviewable artifact landed.

## Scope

Brainstormed whether/how to fold an external RL fine-tuning project ("ZombieE" — GRPO/LoRA on
Qwen2.5-3B, multi-rubric reward, matched-baseline eval) into Cassandra to make a sellable
product, then compiled the conclusion into `docs/RL_MERGE_PROPOSAL.md` for partner review.

## Why (the decision, not just the diff)

The load-bearing insight: ZombieE's chronic weakness (a **gameable reward** — scan-spam
exploit, heuristic ceiling) is exactly what Cassandra's **deterministic grounding verifier**
(`grounding.py` / `oracle.py`) fixes. A deterministic verdict *is* a verifiable reward in the
sense the frontier RL market means it. So rather than a code merge (rejected — disjoint stacks)
or leading with model fine-tuning (rejected as the wedge — open-weights only, heavy sell), the
proposal is:

> A private, verifiable, self-expanding **benchmark of the customer's own agent** — grown by an
> **RL adversary** whose reward is Cassandra's verifier, graded by the deterministic oracle.

Eval-first (Cassandra's existing buyer/brand/wedge), with an RL-training upsell later because
every case is already an `(environment + verifiable reward)`.

Market was verified live (2026-07-02): the RL-environments market is real and huge (Anthropic
$1B+/yr; Surge/Mercor/Mechanize/Prime Intellect), but selling *generic envs to labs* is a trap
against the data-foundry incumbents — so we target the **agent owner**, not the lab. Sources are
in the proposal doc.

## Changes

- **New** `docs/RL_MERGE_PROPOSAL.md` — full proposal: two-project context, rejected ideas,
  verified market check, the product, the technical merge table (which Cassandra modules map to
  reward/adversary/gate), business model, honest risks, open decisions, sequencing. Committed
  `e101320`, pushed to `origin/cassandra-v2`.
- **New** this session note.

## Verification

- Doc committed as a **single file** (`git diff --cached --stat` confirmed only the proposal was
  staged); B1/B2 working tree left untouched. Push succeeded (`d43a495..e101320`).
- No code changed → no tests to run.

## Open items

- **Partner review** of `docs/RL_MERGE_PROPOSAL.md` is the next step.
- The proposal's own **go/no-go gate**: run ZombieE's matched-baseline experiment to prove an RL
  adversary finds failures the static `synthesizer.py` misses. Until then RL is unproven for
  this use.
- Keep this **behind** the CI-gate wedge and `EVAL_PLAN.md` B3 — it is a Phase-C surface, not a
  pivot.
- B1/B2 grounding-verifier working tree remains **intentionally uncommitted** (see
  `2026-07-02-grounding-verifier.md`).
