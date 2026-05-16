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
- 0:10 On the right, **Cassandra's alert fires.** The offending Phoenix span turns red
  with a written annotation: `hallucination · 0.93 · fabricated refund policy; tool
  get_refund_policy returned no data`.
- 0:20 Cut to the real Phoenix UI showing that annotation on that span — *this is
  Phoenix doing exactly what Phoenix is for, but automated.*
- 0:28 One spoken line: *"A production agent just lied to a customer. No human saw it.
  Cassandra did — in eight seconds."*

> This 30s decides the score. It must be visibly real and hard to fake with a wrapper.

### 0:30–1:15 — From failure to dataset

- Show the Diagnostician rationale panel (why it's a hallucination, not just that it is).
- Cassandra auto-generates **12 adversarial trap prompts** (different regions, phrasings,
  edge cases) with expected-correct answers.
- Cut to the real Phoenix **dataset** `cassandra-hallucination-…` populated live.
- Line: *"It didn't just flag the bug — it turned one failure into a permanent
  regression suite."*

### 1:15–2:15 — Proving the fix with numbers

- Phoenix **experiment** runs the dataset against the current prompt: **3/12 pass.**
- Cassandra proposes a hardened system prompt; show the **unified diff** (adds an
  explicit "refuse and escalate if policy data is missing" rule).
- New prompt registered as a **version in Phoenix prompt management.**
- Re-run: candidate prompt **11/12 pass.** Show the before/after bars side by side.
- Line: *"A tested fix — not a hunch — with the A/B already queued. One click to ship."*

### 2:15–3:00 — The recursive close

- One quiet beat: open the `cassandra-meta` Phoenix project. *"And the agent that watches
  agents? It's observable in Phoenix too."*
- Single architecture frame (5 seconds, on screen, not narrated in depth): Gemini 3 ·
  ADK LoopAgent · Vertex AI Agent Engine · Arize Phoenix MCP.
- Impact line: *"Every team running LLMs in production solves this with humans staring at
  dashboards. Cassandra is the human you don't have to hire."*
- End card: **Cassandra — an agent that babysits agents.** Repo + hosted URL on screen.

---

## Narration Script (tight, ~150 words spoken total)

> "A production support agent just told a customer about a refund policy that doesn't
> exist. No human caught it. Cassandra did — in eight seconds. It read the trace,
> diagnosed a hallucination caused by a failed tool call, and annotated the exact span
> right inside Phoenix. Then it turned that single failure into a twelve-case adversarial
> dataset and ran a Phoenix experiment: the current prompt passes three of twelve. So
> Cassandra wrote a hardened prompt, versioned it in Phoenix, and re-ran the experiment —
> eleven of twelve. A tested fix with the A/B already queued. And the agent that watches
> agents is itself observable in Phoenix. Every team running LLMs in production does this
> by hand today. Cassandra is the engineer you don't have to wake up at 2am."

---

## Recording Checklist

- [ ] Deterministic seeder verified — incident reproduces every take (NFR-2, R3).
- [ ] Latency dry-run: catch within 10s on camera (NFR-1). If slow, pre-stage and cut.
- [ ] Fallback clip of the full loop pre-recorded as insurance (R3).
- [ ] Phoenix tabs pre-opened, zoomed, logged in — no fumbling on screen.
- [ ] Numbers chosen for contrast: baseline ≤4/12, candidate ≥10/12 (AC-3).
- [ ] Final cut ≤ 3:00 exactly; captions burned in; audio leveled.
- [ ] Repo URL + hosted URL visible on the end card.
