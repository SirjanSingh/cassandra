# Cassandra: positioning, one page

## What it is

**Cassandra catches when your AI agent states a fact its tools never gave it, and turns each one into a tested prompt fix plus a permanent regression test.**

Think of it as Sentry for wrong answers. It watches the agent's traces after the fact. It never sits in the request path.

## Who it's for

Teams running **tool-using agents where one confidently wrong number costs money or trust**: fintech, insurance, health, travel and logistics, regulated support.

To qualify, three things must be true:
- the agent calls tools,
- its answers contain checkable specifics (amounts, dates, places, statuses),
- a wrong specific is expensive.

## The problem, in numbers

Measured on an honest agent with a normal prompt and real APIs (`poc/travelpal/`):
- **14–30% of answers** stated something no tool backed: visa fees, taxes and limits from memory, the wrong city, the wrong weekday.
- Every one of them sounded fine, and none raised an error.
- The cliché failure ("tool fails → bot invents the result") was rare: it never made up an exchange rate in 22 unsupported-currency questions. The real failures are answering beyond the tools and trusting a wrong tool result.

## What Cassandra does that others don't

| | Typical eval / observability tool | Cassandra |
|---|---|---|
| How a bad answer is detected | An LLM judge's opinion | A **rule over the tool-call log** first; an LLM only when the rule can't decide |
| False alarms | High. Our LLM judge alone: 37–53% precision | **100% precision on unseen questions** (11/11), 73% recall |
| Evidence | "The judge thinks so" | Cites the exact tool call that is missing or failed |
| After detection | A dashboard | A proposed prompt fix, measured before/after. Ours: 30% → 6% bad on unseen questions |
| Data residency | Usually SaaS + external LLM | The rule layer runs anywhere, with no LLM and no data leaving |

## How a customer adopts it (smallest step first)

1. **Scan.** Send exported logs, get back a report of which answers had no source. No code change on their side.
2. **Prove the fix.** Expose a `/chat` endpoint; Cassandra replays and measures candidate prompts.
3. **Guard.** The CI gate blocks prompt edits that bring old failures back; fixes arrive as PRs.

## Pricing (hypotheses to test, not decided)

- Free open-source CLI (scan + CI gate), so developers can find it.
- Paid pilot for one agent over 6 weeks, about $2–5k, with a written success metric.
- Then per supervised agent per month; self-hosted enterprise licence later.

## What it is not

- Not an autonomous self-healing agent: a human approves every change.
- Not a general "is this answer good?" grader: it checks *specific facts against tools*.
- Not a fix for wrong-place or wrong-date errors yet: those need code fixes, and Cassandra can't see them today.

## What we still have to prove

That a real team, shown its own number, wants this kept running. That is the goal of the 30-day plan (`docs/30_DAY_PLAN.md`).
