# Go-to-market (2026-11-05)

> Part of the strategy set. Master document: [PRODUCT_VISION_AND_COMPANY_ROADMAP.md](PRODUCT_VISION_AND_COMPANY_ROADMAP.md).
> Builds on `docs/OUTREACH.md` and `docs/30_DAY_PLAN.md` (on `feature/nli-and-hindi`). Those stay the
> operational checklist for this month; this document sets the longer arc.

## 1. Principles

1. **Distribution is the research.** The strongest asset this team has built isn't a feature. It's
   *honest measurement of how agents actually fail*:
   - Task 0 on 1,980 trajectories;
   - the TravelPal held-out set;
   - the failure-anatomy probe.

   Developers share rigorous, surprising, reproducible findings. They ignore "AI-powered X".
2. **Lead with the problem developers already feel**: "my LLM-judge alerts are noise" and "my agent did
   the wrong thing and said it was done". Don't lead with "hallucination", which is a crowded word our own
   data says is rarer than assumed.
3. **Never overclaim.** Every number names its agent, sample size and labeller. `OUTREACH.md` already says
   this. Make it a rule.
4. **Free must be genuinely useful offline.** The OSS CLI is the funnel, the server is the business. No
   telemetry by default: regulated users must be able to run it air-gapped. Measure the funnel with
   explicit, opt-in "share your report" actions instead.
5. **Hand-to-hand first.** No paid acquisition until retention is proven.

## 2. Messaging

| Use | Avoid |
|---|---|
| "Deterministic checks for tool-using agents: every flag comes with the receipt." | "Sentry for AI agents" (Raindrop's line, and the literal Sentry ships it free) |
| "Your LLM-judge alerts cry wolf. Ours cite the tool call." | "Stops hallucinations" |
| "Find where your agent said 'done' and wasn't." | "Self-healing agents" / "autonomous fixes" |
| "Turn production failures into replayable tests: no live tools, no flakes." | "Bots make things up 30% of the time" (one test bot, self-labelled) |
| "Runs on your laptop. Nothing leaves." | Anything implying we host Phoenix |

## 3. What to publish (in order)

| # | Asset | Content | Why it spreads | Owner / effort |
|---|---|---|---|---|
| 1 | **Research post: "We tried to catch agents making things up. Here's what actually breaks."** | Task 0 (reproducible, 1,980 trajectories); the failure-anatomy probe (94.6% of failures are wrong actions; swallowed-error check at 80% precision); TravelPal (when tools are narrow, answering beyond them is the failure); why LLM judges can't be the alarm (our 37–53% + arXiv 2606.09863). Scripts linked | Honest negative result + counter-intuitive data + reproducible | ~3 days; both founders review numbers |
| 2 | **Open benchmark repo**: labelled turns (TravelPal 148 turns + labels), tau-bench anatomy scripts, check precision table | Invites others to beat it; becomes our regression suite | Credibility with evaluators | 2 days (after licence check on tau-bench data reuse; ship scripts that download it, not the data) |
| 3 | 5-minute quickstart + sample logs | `pip install` → `init` → `scan` on bundled logs | Lets readers of #1 act immediately | Exists in part (`docs/SCAN.md`) |
| 4 | GitHub Action + "add agent regression tests to CI" guide | The retention surface | Lands in repos | After `test` ships |
| 5 | Framework recipes: OpenAI Agents SDK, LangGraph, Pydantic AI (record → scan → keep → test) | Where agent builders search | SEO + community listings | 1 day each |
| 6 | Short video: "Find every time your agent said 'done' and wasn't, in 5 minutes" | Real run on a public sample | Shareable on LinkedIn/X/YouTube | 0.5 day |
| 7 | Talk proposal: "LLM judges are not alarms: measuring agent failure on 2,000 trajectories" | Meetups first, then conference CFPs | Credibility | Ongoing |

## 4. Channel plan by stage

### First 100 users (now → ~week 10): hand-to-hand

**Who.** Teams with a **tool-using agent in production or pilot** whose answers or actions have consequences:

- support bots that touch orders or refunds;
- fintech and insurance assistants;
- travel booking;
- internal IT/HR agents with write tools.

**Where:**

- The founders' own networks and alumni.
- The founders' local startup ecosystem. The commit history is IST-based, and the repo already supports
  Hindi, which is relevant to India's fintech and support-automation startups.
- Arize/Phoenix community Slack and Langfuse GitHub Discussions. Be helpful there; don't spam.
- r/LLMDevs, the LangChain/LangGraph Discord, the OpenAI developer forum (agents threads).
- Founders of YC/accelerator AI-agent startups (public batch lists).

**The offer.** A "free agent failure audit". They export about 1 week of logs (or traces). We write the
contract with them on a 45-minute call, run `scan`, hand-check every flag, and send a report plus a
regression suite. Concierge onboarding is deliberate: it's how we learn what `init` must automate.

**Conversion goals:**

- 20 conversations → 8 log exports → 5 reports → 3 "run it again / how do we keep this?" → 1 paid pilot.
- `OUTREACH.md` estimates 1–3 replies per 10 cold messages, so start warm.

**Metrics:** replies, log exports, flags confirmed by the team, requests for a re-run, pilot asks.

### 100 → 1,000 (months 3–6): open-source launch

Launch only when:

- `init` gets a stranger to a useful contract in < 30 min;
- precision per check is published;
- at least 2 design partners agree to be quoted.

**Sequencing:**

1. Launch week:
   - publish research post #1 → submit as "Show HN: …" with the reproducible scripts;
   - cross-post to r/MachineLearning (research flair) and r/LLMDevs;
   - founders post on LinkedIn/X.
2. Same week: the benchmark repo (#2) and quickstart (#3).
3. Two weeks later: GitHub Action + Marketplace listing (#4).
4. Monthly: one framework recipe (#5) and one "failure of the month" teardown from public agent traces.
   Only use data we're allowed to publish.

**Integration listings:**

- Ask Langfuse and Phoenix to list the importer in their integrations pages. Both run integration
  directories, but listing is at their discretion.
- Contribute an example to the OpenAI Agents SDK / LangGraph docs if maintainers accept.

**Metrics:**

- weekly unique scan runs among opt-in report shares;
- GitHub issues from strangers;
- Action installs;
- the number of external contracts contributed.

### 1,000 → 10,000 (months 6–18): ecosystem

- **Be the default "verify" step in agent templates.** Ship a `verify` stage in popular starter repos via PRs.
- **Community check packs** (refunds, bookings, KYC), each with its own precision table. Contributors get credit.
- **Public leaderboard** of agent action-correctness on open benchmarks, using our checks as the evaluator.
  Re-run it when new models ship. Every release creates news.
- **Partnerships:**
  - tracing vendors: we are an add-on to them, not a competitor;
  - agent-platform consultancies: they implement agents for regulated clients and need a verification
    artefact to hand over.
- Paid content only after product-led retention exists. Sponsor one practitioner newsletter or podcast as a test.

## 5. Sales motion (for the commercial tier)

- **Founder-led.** The pilot is a written success metric (e.g. "≥ N confirmed failures/month caught at
  ≥ 80% precision; regression suite in CI") over 6 weeks, at a fixed fee. Charge from the first pilot:
  the 2026-08-05 note's rule, "free pilots teach nothing about WTP", stands.
- Buyer: head of AI/ML engineering or the agent platform lead. Champion: the engineer on call for the agent.
  For fintech and insurance, expect a security/compliance reviewer. The local-first CLI and self-hosted
  server are the answer.
- No Stripe, no self-serve pricing page until about 10 paying teams. Invoices.

## 6. What not to do

- Product Hunt before there's a stranger-proof `init`. It burns the launch.
- Paid ads, SEO farms, or "AI agent" listicles.
- Cold-email blasts. They damage reputation in a small community.
- Claiming precision numbers from our own test bots as if they generalise.
- Building the hosted dashboard to "look real" for outreach. The report *is* the demo.
