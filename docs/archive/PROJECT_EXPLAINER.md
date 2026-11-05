# Cassandra — Explained From Scratch (the whole thing, in plain language)

> **Status:** plain-language explainer (2026-06-28), branch `cassandra-v2`. For a reader who
> wants to understand *everything going on* in this project without assuming jargon.
> **Reads with:** [`PROJECT_PLAN.md`](../PRODUCT_PLAN.md) / [`EVAL_PLAN.md`](../EVAL_PLAN.md)
> (the deep plans), [`MARKET_AND_ALTERNATIVES.md`](MARKET_AND_ALTERNATIVES.md) (competition +
> the v2 decisions), [`LEARNING_RESOURCES.md`](LEARNING_RESOURCES.md) (what to study).
> The authoritative *technical* deep-dive is `docs/SYSTEM_DESIGN.md`; this doc is the gentle
> on-ramp to it.

---

## 1. The one-sentence version

**Cassandra is a robot supervisor for other AI agents:** it watches an AI agent doing its job,
notices when it screws up, figures out *why*, writes a fix, proves the fix actually works, and
makes sure that mistake can never come back — automatically.

---

## 2. The problem it solves (why anyone cares)

Companies are putting AI agents in front of customers (support bots, ops assistants). These
agents have a nasty habit: when a tool returns nothing, **they make stuff up** ("hallucinate")
instead of admitting they don't know. Example: a customer asks "what's your refund policy in
Germany?", the agent's database has no German policy, and instead of saying "I don't have
that," it **invents** a confident-sounding 30-day policy. That's a real, reputation-damaging
failure — and nobody notices until a customer complains.

Today, catching this means a human reading transcripts. That doesn't scale. **Cassandra is the
machine that reads the transcripts, catches the lie, and fixes the agent.**

---

## 3. The cast of characters

- **The Patient** (`patient/` folder) — a deliberately *fragile* demo agent called "ShopBot."
  It's a fake online-store assistant that's been intentionally built to hallucinate, so we have
  something broken for Cassandra to fix. Think of it as a crash-test dummy.
- **Cassandra** (`cassandra/` folder) — the supervisor. The actual product.
- **Phoenix / (soon) Langfuse** — the "black box recorder." The Patient writes a record of
  everything it does here; Cassandra reads those records. The two agents **never talk
  directly** — they communicate *only* through this recorder. (That separation is deliberate
  and important: it means Cassandra can supervise *any* agent, not just ShopBot.)
- **The dashboard / cockpit** (`web/`, `dashboard/`) — the live screen where you watch
  Cassandra work in real time.

---

## 4. How Cassandra works — the 8-step loop (the core of everything)

Cassandra runs one failure through an assembly line of 8 stages. Each stage is its own file in
`cassandra/`. One "Incident" object travels down the line, picking up information at each
station (like a car on an assembly line gaining parts):

1. **Watcher** (`watcher.py`) — polls the black-box recorder for new agent activity. "Anything
   new happen? Anything look off?" Picks one incident to investigate.
2. **Diagnostician** (`diagnostician.py`) — the judge. Looks at what the agent was asked, what
   it answered, and what its tools returned, then classifies the failure: *hallucination*,
   *tool-failure*, *prompt-drift* (went off-character), or *ok* (no problem).
3. **RootCauseAnalyst** (`rootcause.py`) — "*why* did this happen?" Diagnoses the underlying
   cause, not just the symptom.
4. **Synthesizer** (`synthesizer.py`) — invents a *batch of new test questions* designed to
   trigger the same failure. This is how one real bug becomes a permanent test suite.
5. **Evaluator (baseline)** (`evaluator.py`) — runs those tests against the agent's *current*
   prompt and scores it. Establishes "here's how bad it is right now."
6. **Patcher** (`patcher.py`) — writes an *improved* prompt that should fix the problem.
7. **Evaluator (candidate)** — runs the same tests against the *new* prompt. "Did my fix
   actually help?"
8. **TraceReplay + RedTeam** (`replay.py`, `redteam.py`) — replays the *original* failing
   question to confirm it's now fixed, then *attacks* the new prompt with adversarial inputs to
   make sure the fix didn't open new holes.

The result is written back into the black-box recorder (annotations, datasets, improved
prompts), so the whole thing is auditable. This entire loop lives in
`loop_agent.py:SupervisionPipeline.run_once()`.

---

## 5. The big idea that makes it special (and the current weakness)

**The weakness reviewers attacked:** "You use an AI to judge another AI. How do you know the
*judge* is right? You're just an API wrapper." That's a fair hit — if the core decision is just
another AI opinion, it can be wrong and it's not defensible.

**The fix (this is the most important concept in the project):** for a tool-using agent, you
**don't need an opinion — you have the facts.** When ShopBot calls `get_refund_policy("DE")`
and the tool returns `{found: false}`, that is a *fact*: there is no German policy. So if the
agent's answer states a German policy anyway, it is *provably* lying — you can check it with
plain code, no AI judgment required.

This is **"deterministic" evaluation**: same input → same provable answer, every time, like a
calculator. The plan in `EVAL_PLAN.md` is to make this fact-checking the *primary* engine and
demote the AI judge to a rare fallback (only for fuzzy cases where there are no hard facts to
check). **That shift — from "an AI says so" to "the records prove it" — is what turns Cassandra
from an API wrapper into real, defensible technology.**

There's a specific bug to fix first (called "F1"): right now, in the *real* pipeline, the tool
records aren't actually reaching the judge (they reach it only in the self-test). So the
impressive "100% accuracy" number measures a different code path than what really runs. Fixing
that is step one of v2. (Details: `EVAL_PLAN.md §5`.)

---

## 6. What the hackathon forced, and what v2 changes

This started as a **Google Cloud + Arize hackathon** entry, which forced three choices that
aren't necessarily the *best* product choices. v2 is about un-forcing them:

| Thing | Why it was there | v2 decision | What it buys you |
|---|---|---|---|
| **Arize Phoenix** (the recorder) | Arize track rule | ✅ **Switch default to Langfuse**, keep Phoenix as an option | Langfuse is MIT-licensed → you can legally build a paid product on it; Phoenix's license forbids that |
| **Google Vertex Gemini** (the AI model) | "must use Gemini" rule | ✅ **Adopt LiteLLM** | One interface to 140+ models; customers use whatever model they want; not locked to Google |
| **Google Cloud / ADK** (where it runs) | "built with Agent Engine" rule | Containerize; make Google-specific bits optional | Runs anywhere — any cloud or on-prem |

The good news (in `PRODUCT_PLAN.md`): the code was already built with clean "swap points," so
these are *swaps*, not rewrites.

---

## 7. Decisions already made ✅ and what's still open

**Already decided:**
- ✅ **Telemetry backend → Langfuse** (MIT, sellable, vendor-neutral via OTLP). Phoenix stays
  as an optional adapter.
- ✅ **Model layer → LiteLLM** (one interface, 140+ providers, replaces the hand-rolled router).

**Still to pick — with my recommendation for each:**

1. **Self-hosted models (running the AI on your/customer's own machines) — now or later?**
   → **Recommendation: LATER.** It's the "enterprise unlock" (banks/hospitals that can't let
   data leave their network), but it adds scope before you have customers. Build the hook for it
   (LiteLLM already supports Ollama/vLLM), but don't prioritize it until a real enterprise lead
   asks. *Timing call, not a now-or-never.*

2. **The wedge (your first, easiest thing to get people to adopt)?**
   → **Recommendation: CI-GATE-FIRST.** Lead with "add Cassandra to your pipeline and it blocks
   prompt changes that make your agent worse" — like a spell-checker for AI quality before
   release. It's the lowest-friction way in, and it's exactly how your closest competitors
   (Braintrust, Opik) succeeded. Expand into the full autonomous loop later.

3. **Open-source license for the free core?**
   → **Recommendation: PERMISSIVE (MIT or Apache-2.0).** This is what makes developers
   comfortable adopting it and dragging it into their companies. Keep the paid stuff (hosting,
   team features) separate. *Do not* inherit Phoenix's restrictive license.

4. **Keep the Google Cloud deployment as an option, or drop it?**
   → **Recommendation: KEEP IT OPTIONAL.** It's cheap to maintain and nice for teams already on
   Google's Vertex. Just make it *not* the default.

5. **Business model?**
   → **Recommendation: OPEN-CORE.** Free open-source core (the loop, the CI gate, the verifier,
   the MCP server) drives adoption; paid hosted + team/enterprise features make money. This is
   the proven playbook (GitLab, HashiCorp, Langfuse itself). Detail in `PRODUCT_PLAN.md §4`.

6. **Brand/name** — keep "Cassandra" or rename for the commercial product? *(Your call;
   nothing technical depends on it.)*

---

## 8. The honest competitive picture (so you know who you're up against)

Three "rings" of competitors (full detail in `MARKET_AND_ALTERNATIVES.md`):
- **Ring 1 — watchers** (Langfuse, LangSmith, Arize): just show you traces. *Crowded.* Don't
  compete here — **run on top of them.**
- **Ring 2 — graders** (DeepEval, Braintrust, Opik): score quality. Differentiated.
- **Ring 3 — fixers** (autonomous detect→fix→verify): **almost empty — this is your lane.**
  Only Braintrust and Opik are close, and both still lean on an AI judge/optimizer as the
  product.

**Your moat is the *combination*, not any single piece:** deterministic fact-checking **+** the
autonomous fix-and-verify loop **+** the "flywheel" (every real bug caught becomes a permanent
test the customer owns and can't get elsewhere) **+** working on anyone's stack. No competitor
has all four. The warning: Opik and DeepEval are *already* adding deterministic checks, so move
on the eval re-architecture before that edge erodes.

---

## 9. What to actually do next (the order)

1. **Fix F1** (make the tool records reach the judge in the real pipeline) + add a test that
   proves it. This reveals your *true* accuracy. *Smallest change, biggest credibility win.*
2. **Build the deterministic verifier** (`EVAL_PLAN.md` L1) — the moat.
3. **Swap in Langfuse** (the telemetry decision) and **LiteLLM** (the model decision).
4. **Package the CI-gate wedge** (a GitHub Action) → first users.
5. Then revisit the open decisions in §7 as real usage teaches you what matters.

Everything in this document maps back to the deeper plans: `EVAL_PLAN.md` (the eval rebuild),
`PRODUCT_PLAN.md` (the independence + business plan), and `MARKET_AND_ALTERNATIVES.md` (who else
is out there). This file is just the map; those are the territory.
</content>
