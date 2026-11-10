# Strategy: what Cassandra is, who pays, and why

*Decided 2026-11-10. Replaces the earlier positioning (a "meta-agent" that supervises agents
through Phoenix). Revisit at each gate in [ROADMAP.md](ROADMAP.md).*

## 1. The product in one sentence

**Cassandra checks a bot's answers against the data the bot was given, and shows every
statement that data doesn't back.**

We don't say "catches hallucinations". Buyers no longer believe that modern models make
things up wholesale, and on simple Q&A with good documents they mostly don't (GPT-4 was
wrong in about 4% of answers on RAGTruth). The failure that survives is quieter:

> **The bot had the right data and still said something slightly different.**

It reports the wrong carrier or the wrong hours, says "no parking" when the record says
street parking, or adds a detail nobody gave it. Even GPT-4 did this in about 1 in 4
answers when turning structured data into text ([EVIDENCE.md](EVIDENCE.md)).

## 2. What we cut, and why

Being brutal: we built far more than anyone has asked for.

| Cut | Why |
|---|---|
| 9-stage pipeline (watcher → diagnose → root cause → synthesize → evaluate → patch → replay → red-team) | Never ran on a real customer's bot. Needed Phoenix, a replay endpoint and our demo bot. Too much to explain, install or trust. |
| Arize Phoenix dependency and MCP server | Most companies don't run Phoenix. A required dependency loses them at step one. |
| Auto-generated prompt patches and PRs | Nobody gives an unknown tool write access to their prompts. Earn trust with findings first. |
| Whole-answer LLM judge, jury, NLI layer | Measured: 9% recall on human-labelled data. Replaced by claim-by-claim (43%). |
| Dashboard, React UI, Cloud Run deploy, demo victim bot (ShopBot) | Hackathon scaffolding. |

All of it is preserved on the `feature/nli-and-hindi` branch. If customers later ask for
"and fix it for us", the patcher can come back as a paid add-on.

## 3. Who it's for (ideal customer)

**A company running a customer-facing bot that answers from its own systems,** where a
wrong detail costs money or trust:

- **E-commerce / D2C:** order status, returns, delivery dates
- **Travel and bookings:** fares, times, availability, policies
- **Fintech, insurance, lending:** fees, limits, policy terms (also a regulatory reason to check)
- **SaaS support bots:** plan limits, pricing, feature availability

Signals that a company fits:
- The bot calls APIs or retrieves documents. If it's pure chit-chat, there is nothing to check.
- It handles 1,000+ conversations a month.
- Someone owns "bot quality" (head of CX or support ops, or the engineer who built it).
- They can export logs that include tool results or retrieved text. **This is the #1
  qualifying question.**

**Not for us (yet):** voice bots, internal copilots, coding agents, and companies whose
logs don't capture what the bot was given.

## 4. Business model: open core plus done-for-you

The code is open source (Apache-2.0) and free to self-host. That is our distribution: an
engineer can try it in a minute, and that is how we get in the door. Companies pay for what
saves them time or carries risk.

| Offer | What they get | Price (hypothesis, to be tested) |
|---|---|---|
| **Free (open source)** | CLI, SDK and HTTP API. Self-hosted, bring your own model. | $0 |
| **Answer Audit** (service, *first thing we sell*) | We scan up to 10k of their conversations and hand over the report, a 30-min walkthrough and a ranked fix list (prompt or data changes). | **$750 / ₹50,000 per bot.** The first 3 are free in exchange for a case study and permission to quote numbers. |
| **Guard** (subscription, after 2+ audits) | Live checking via `cassandra serve`, a review queue where their team confirms or dismisses flags, Slack/email alerts, a weekly quality report, and support. | **From $400 / ₹30,000 per bot per month**, up to 50k checked answers |
| **Hosted** (later) | The same as Guard, run by us. | Per 1,000 checked answers; set once we know real volumes |

Why this order:
1. **Audits make money in week 4, not month 6.** They need nothing we haven't built.
2. **Every audit is customer research.** We see real logs, real failure rates and what
   people actually care about.
3. **Every audit produces labels.** The customer's "real / not real" verdicts tell us our
   precision on *their* data, and that is the honest number for selling Guard.

**Unit economics, roughly:** the claim check costs roughly $0.5–1 per 1,000 answers on
gpt-4o-mini. Guard at $400 for 50k answers costs about $25–50 in model calls, so the margin is
in the software and review workflow, not reselling tokens.

## 5. Competition: honest view

| Who | What they do | Where we differ |
|---|---|---|
| AWS Bedrock *contextual grounding*, Azure *groundedness detection* | Built-in grounding checks inside each cloud | Ours works on any stack and any model (including local), understands **tool calls**, and gives a report a non-engineer can read |
| Arize, Galileo, Patronus (Lynx), Braintrust | Observability or eval platforms with faithfulness metrics | They are platforms you adopt. We are one check that runs on your exported logs today, plus a person who walks you through it. |
| Ragas, TruLens, DeepEval | Open-source eval libraries (faithfulness metrics) | Built for ML engineers running experiments. We target the person who owns the live bot, with tool-call-aware checks and a shareable report. |
| Doing nothing / sampling chats by hand | Support leads read 20 chats a week | We read all of them and point at the 2% worth reading |

**The moat is thin, and that's OK at this stage.** What we can own is the narrow focus
(tool-using customer-facing bots), the done-for-you audit, and a growing set of real
labelled failures from audits that makes our checks better on exactly this kind of bot.
If a big platform ships this as a checkbox, we lose the generic case. That's why we start
from service and specific verticals, not a self-serve SaaS.

## 6. The pitch

**One line:**
> "Your bot read the right data and still told customers something different. Cassandra
> finds those answers."

**Proof** (always say how it was measured):
> "On a public benchmark with human labels, our check finds 43% of bad answers, where a
> standard AI judge finds 9%. About one in four of our flags is a real problem, so it tells
> your team which handful of chats to read."

**The ask:**
> "Send us a few hundred exported conversations (with what the bot looked up) and we'll
> send back a report in 3 days. Free for the first three companies."

## 7. What would make us change course

See the gates in [ROADMAP.md](ROADMAP.md). In short:
- If audits keep finding little that companies care about, the problem is too small.
- If their logs rarely include tool results or retrieved text, the integration cost is
  too high.

Either way, we pivot. The fallback already scoped: an **agent action firewall**, which
checks a bot's *actions* (refunds, cancellations, emails) against company rules before they
execute. It reuses the same engine, SDK and API.
