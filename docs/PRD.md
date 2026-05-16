# Cassandra — Product Requirements Document (PRD)

**Version:** 1.0 (Day-0) · **Owner:** Solo builder · **Last updated:** 2026-05-17
**Status:** Approved for build · **Deadline:** 2026-06-12 02:30 IST (= 2026-06-11 14:00
PDT, verified on official Devpost page 2026-05-17) · **Target ship:** 2026-06-11 (buffer)

---

## 1. Vision

Cassandra is a meta-agent: an autonomous agent whose sole responsibility is the
**continuous quality supervision of other LLM agents in production.** It observes a target
agent through its Arize Phoenix telemetry, detects failure modes, converts real failures
into reproducible evaluation assets, validates fixes experimentally, and proposes
deployable prompt patches — closing the observability → evaluation → improvement loop with
no human in the path until the final approval gate.

**Elevator pitch:** *"It is an agent that babysits agents. When your production agent
hallucinates, Cassandra catches it, proves it with an eval, and hands you a tested fix
before your on-call engineer has finished their coffee."*

## 2. Problem Statement

LLM agents fail in ways traditional monitoring cannot see:

- **Hallucination** — confident, fluent, factually wrong output (e.g. inventing a refund
  policy that does not exist).
- **Prompt drift** — behavior degrades after a model/version change while the prompt is
  unchanged; or instruction-following decays over long contexts.
- **Tool-call failure** — a tool errors or returns malformed data and the agent papers
  over the gap with a fabrication instead of surfacing the error.

Current mitigation is **manual and reactive**: humans sample traces, eyeball outputs,
hand-author eval datasets, and tweak prompts by intuition. This does not scale with agent
count or traffic, has high latency to detection, and misses the long tail entirely.

## 3. Goals & Non-Goals

### Goals

- G1 — Detect the three failure classes above from live Phoenix traces with explainable,
  per-span verdicts.
- G2 — Write verdicts back into Phoenix as span annotations (failures are visible in the
  customer's existing tool, not a separate silo).
- G3 — Auto-synthesize a reproducible adversarial eval dataset from any confirmed failure.
- G4 — Quantify any proposed fix with a Phoenix experiment (LLM-as-judge, current vs.
  candidate prompt).
- G5 — Propose a versioned, A/B-ready prompt patch via Phoenix prompt management.
- G6 — Present the entire loop on a live dashboard suitable for a 3-minute demo.

### Non-Goals (explicitly out of scope for v1)

- NG1 — Auto-deploying patches without human approval (we *queue* an A/B; we do not flip
  it live).
- NG2 — Supervising non-LLM systems or infra metrics (that is the Dynatrace bucket's job).
- NG3 — Multi-tenant SaaS, auth, billing, RBAC.
- NG4 — Fine-tuning or model training. Cassandra only touches prompts and evals.
- NG5 — Supporting observability backends other than Phoenix.

## 4. Target Users & Personas

| Persona | Need | How Cassandra serves it |
|---------|------|--------------------------|
| **LLM Platform Engineer** ("the on-call for agents") | Know within minutes when an agent regresses, with a reproducible case | Real-time alerts + annotated failing span + auto eval dataset |
| **Applied AI / Prompt Engineer** | A tested prompt fix, not a hunch | Candidate patch with measured pass-rate delta from a Phoenix experiment |
| **Eng Manager / Hackathon Judge (Arize SE)** | See Phoenix used deeply and correctly | Near-full Phoenix MCP surface exercised in a coherent autonomous loop |

Primary persona for the demo narrative: the **Platform Engineer** woken at 2am because a
support agent is inventing policies.

## 5. User Stories

- **US-1** As a platform engineer, I want Cassandra to watch my agent's Phoenix project so
  that failures are caught without me sampling traces.
- **US-2** As a platform engineer, I want each detected failure annotated on the exact
  Phoenix span so that I can see *why* it was flagged in the tool I already use.
- **US-3** As a prompt engineer, I want a failure turned into a 12-row adversarial dataset
  so that the bug is reproducible and regression-tested forever.
- **US-4** As a prompt engineer, I want a Phoenix experiment comparing the current and
  proposed prompt so that I trust the fix with numbers, not vibes.
- **US-5** As a platform engineer, I want the proposed patch versioned in Phoenix prompt
  management with an A/B queued so that rollout is one approval click.
- **US-6** As a judge, I want to watch this entire loop happen live in under 3 minutes.

## 6. Functional Scope (summary — full detail in REQUIREMENTS.md)

| Capability | In v1 |
|------------|-------|
| Scheduled trace ingestion from Phoenix via MCP | ✅ |
| Gemini-3 LLM-as-judge classification of spans | ✅ |
| Write-back annotations to Phoenix | ✅ |
| Adversarial dataset synthesis + upload to Phoenix | ✅ |
| Phoenix experiment (current vs candidate) | ✅ |
| Prompt patch proposal + Phoenix prompt versioning | ✅ |
| A/B experiment queued (not auto-promoted) | ✅ |
| Live dashboard (alert feed → span → dataset → patch diff → experiment link) | ✅ |
| "The Patient" — a deliberately fragile demo victim agent | ✅ |
| Deterministic incident seeder for reliable demo capture | ✅ |
| BigQuery long-term span analytics | ⚠️ stretch only |
| Slack/email alerting | ❌ out of scope |
| Auto-promotion of winning prompt | ❌ NG1 |

## 7. Success Metrics

### Hackathon success (the real KPI)

- **Primary:** Top-3 placement in the Arize bucket ($2k–$5k).
- Submission accepted: public repo + top-level LICENSE + hosted URL + ≤3-min video +
  Devpost form + Arize track selected.

### Product success metrics (demonstrated on camera)

- **Detection latency:** seeded failure → annotated Phoenix span in **< 10 seconds**.
- **Diagnostic precision:** ≥ 90% correct classification on the seeded trap set
  (hand-labeled, ~20 cases).
- **Eval lift demonstrated:** candidate prompt beats current prompt by a visible margin
  (target: current ≤ 4/12 pass, candidate ≥ 10/12 pass on the synthesized dataset).
- **MCP surface coverage:** ≥ 5 distinct Phoenix MCP tool families exercised end-to-end
  (spans, annotations, datasets, experiments, prompts).

## 8. Constraints & Assumptions

- Solo builder, ~25 working days.
- Mandatory stack: Gemini 3, Agent Builder/ADK, ≥1 partner MCP (Phoenix). Non-negotiable.
- Phoenix Cloud free tier is sufficient for demo scale; self-host on Cloud Run is the
  fallback if cloud limits bite.
- Judges will **not** run the code — the video and hosted URL carry the submission.
- Assumption: Phoenix MCP exposes tools for spans, annotations, datasets, experiments, and
  prompt management. **Validated by a Day-1 spike before any feature work.**

## 9. Risks (see IMPLEMENTATION_PLAN.md §Risks for mitigations)

- R1 — Phoenix MCP tool surface differs from assumptions → Day-1 enumeration spike.
- R2 — Gemini 3 / Agent Engine quota or availability → confirm Day 1, Cloud Run fallback.
- R3 — Failure not reproducible on camera → deterministic seeder, never live randomness.
- R4 — Scope creep → NG list is binding; stretch items only if ahead at Day 20.

## 10. Release Definition (Definition of Done)

The product is "done" when, from a clean deploy, a single seeded customer message causes —
with no human action — an annotated Phoenix span, a synthesized Phoenix dataset, a
completed Phoenix experiment showing a pass-rate lift, and a versioned candidate prompt
with an A/B queued, all reflected on the live dashboard within the demo window; and the
repository is public with a detectable top-level Apache-2.0 LICENSE.
