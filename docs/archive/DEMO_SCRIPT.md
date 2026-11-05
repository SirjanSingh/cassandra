# Cassandra — Demo Video Script (≤ 3:00)

The video **is** the submission — judges do not run code. Every second is rationed. No
title card, no "hi my name is," no architecture lecture up front. Open on the wow.

Total budget: **180 seconds.** Record at 1080p+, large readable fonts, cursor highlighting
on, captions burned in (judges often watch muted first).

---

## Shot List

### 0:00–0:30 — The Catch (the only thing that matters)

Split screen. **Left:** the Patient chat. **Right:** the Cassandra dashboard + a Phoenix
tab.

- 0:00 Type into the Patient: *"Hi, what's your refund window for orders shipped to
  Germany?"*
- 0:06 Patient answers confidently and **wrongly**: *"You have a full 90-day no-receipt
  cash refund on all EU orders."* (The `get_refund_policy` tool silently failed; the
  fragile prompt hallucinated.)
- 0:10 On the right, **Cassandra's alert fires** with a **CRITICAL severity** chip. The
  offending Phoenix span turns red with a written annotation: `hallucination · 0.93 ·
  fabricated refund policy; tool get_refund_policy returned no data`.
- 0:20 Cut to the real Phoenix UI showing that annotation on that span — *this is
  Phoenix doing exactly what Phoenix is for, but automated.*
- 0:28 One spoken line: *"A production agent just lied to a customer. No human saw it.
  Cassandra did — in eight seconds."*

> This 30s decides the score. It must be visibly real and hard to fake with a wrapper.

### 0:30–1:05 — Root cause → dataset

- Show the Diagnostician rationale, then the **root-cause** panel: culprit, causal chain
  (`tool miss → prompt gap → fabrication`), and the prescribed fix strategy.
- Cassandra auto-generates **~12 adversarial trap prompts** (different regions, phrasings,
  edge cases) with expected-correct answers.
- Cut to the real Phoenix **dataset** `cassandra-hallucination-…` populated live.
- Line: *"It diagnosed *why* — and turned one failure into a permanent regression suite."*

### 1:05–2:05 — Proving the fix (live, not just a number)

- Live evaluation of the **current** prompt over the dataset: **2/8 pass.**
- Cassandra proposes a hardened prompt; show the **unified diff** ("refuse and escalate if
  policy data is missing"). Registered as a **version in Phoenix prompt management.**
- Candidate evaluation: **8/8 pass** — with a **cost/latency chip**: *"safer **and** ~15%
  fewer tokens."*
- **The money shot — live replay:** the *exact* original Germany question is re-run on the
  patched prompt. Before: the fabrication. After: *"I don't have a verified policy for that
  region; let me escalate."* Judge verdict: **✓ FIXED.**
- **Red-team:** synthesized attacks fired at the live agent — `1/6 → 6/6 survive the patch`.
- Line: *"A tested fix — proven on the very case that broke, with the A/B queued. One click."*

### 2:05–3:00 — The recursive close

- Click **"Grade my own diagnoses"**: Cassandra runs the labeled trap set through its own
  Diagnostician and posts a **diagnostic-accuracy scorecard** (e.g. 91%, per class).
- Open the `cassandra-meta` Phoenix project: *"And the agent that watches agents? It's
  fully traced and graded in Phoenix too — it uses its own observability data to improve."*
  (This is the Arize track's explicit bonus criterion.)
- Single architecture frame (5s): Gemini 3 · ADK LoopAgent · Vertex AI Agent Engine ·
  Arize Phoenix MCP (consumed) · **cassandra-mcp (published)**.
- Impact line: *"Every team running LLMs in production solves this with humans staring at
  dashboards. Cassandra is the human you don't have to hire."*
- End card: **Cassandra — an agent that babysits agents.** Repo + hosted URL on screen.

---

## Narration Script (tight, ~150 words spoken total)

> "A production support agent just told a customer about a refund policy that doesn't
> exist. No human caught it. Cassandra did — in eight seconds. It read the trace,
> diagnosed a hallucination caused by a failed tool call, found the root cause, and
> annotated the exact span inside Phoenix. It turned that one failure into an adversarial
> dataset, scored the current prompt — two of eight — then wrote a hardened prompt,
> versioned it in Phoenix, and proved the fix live: it re-ran the very question that broke
> and the agent now refuses and escalates. Eight of eight, fewer tokens, attacks defeated.
> Then Cassandra graded its own diagnoses and traced its own reasoning back into Phoenix.
> Every team does this by hand today. Cassandra is the engineer you don't have to wake at 2am."

---

## Recording Checklist

- [ ] Deterministic seeder verified — incident reproduces every take (NFR-2, R3).
- [ ] Latency dry-run: catch within 10s on camera (NFR-1). If slow, pre-stage and cut.
- [ ] Fallback clip of the full loop pre-recorded as insurance (R3).
- [ ] Phoenix tabs pre-opened, zoomed, logged in — no fumbling on screen.
- [ ] Numbers chosen for contrast: baseline ≤2/8, candidate 8/8 (AC-3).
- [ ] Replay before/after lands FIXED on camera (FR-RP1) — this is the money shot.
- [ ] Red-team survivor jump visible (e.g. 1/6 → 6/6, FR-RT1).
- [ ] "Grade my own diagnoses" scorecard pre-warmed so it returns fast on camera (FR-SE1).
- [ ] `cassandra-meta` Phoenix project shows Cassandra's own traces (FR-SE2).
- [ ] Final cut ≤ 3:00 exactly; captions burned in; audio leveled.
- [ ] Repo URL + hosted URL visible on the end card.
