# Roadmap: how we proceed

*Starts 2026-11-10. Each phase ends in a **gate**: a yes/no check on real evidence. If a gate
fails, we don't push harder. We change course as written in the gate.*

**What's built today (v0.4.0, branch `focus/answer-check`):**
- The three-layer engine
- `cassandra demo / scan / serve`
- The Python SDK
- HTML/Markdown/JSON reports
- The benchmark scripts

## Phase 0: ship the focused product (week of Nov 10)

| Task | Owner | Done when |
|---|---|---|
| Review this branch, merge `focus/answer-check` → `main` | Kshitij + Sirjan | Merged |
| Publish 0.4.0 to PyPI (`python -m build && python -m twine upload dist/*`) | Kshitij (own token) | `pip install cassandra-ai` → `cassandra demo` works in a clean venv |
| Make the GitHub repo description and README match the one-liner | Kshitij | Done |

## Phase 1: make the flags worth reading, and start conversations (Nov 11 – Nov 24)

Two tracks in parallel. Neither waits for the other.

**Product: cut false alarms.** Today about 1 in 4 flags is real, and a buyer's team will
tire of reading three wrong flags for every right one.
- Add a second pass: re-check only the flagged claims, with the source and a stricter
  question, optionally on a stronger model.
- Also try gpt-4o as the claim checker, and measure the cost difference.
- Tune on RAGTruth **train**; report on **test** once.
- **Target:** at least half of flags real, while still catching at least 35% of bad answers.
- Update docs/EVIDENCE.md with whatever the result is, good or bad.

**Sales: get 3 free audits lined up.**
- Build a list of 30 companies matching the profile in [STRATEGY.md §3](STRATEGY.md) and
  message all of them ([OUTREACH.md](OUTREACH.md)).
- Ask the qualifying question first: *"Can you export conversations together with what the
  bot looked up?"*
- **Target:** 5 calls held, 3 companies agree to send logs.

## Phase 2: free audits (Nov 25 – Dec 8)

For each of the 3 companies:
1. Get the logs. Convert them to our JSONL with a small script if needed; keep the script,
   because it is the start of a connector.
2. Run `cassandra scan --llm`, then **read every flag yourself** before sending anything.
   Remove the obvious false alarms and count them, since that is our precision on real data.
3. Send the HTML report plus a one-page summary: top 3 failure patterns and the fix for each.
4. Hold a 30-min walkthrough. Ask: *"Which of these would you have wanted to know about?
   Would you want this every week? What would that be worth?"*

> **Gate A (Dec 8):**
> - ✅ **Go:** at least 2 of 3 companies confirm we found real problems they didn't know
>   about, and at least 1 asks about continuing or price. Move to Phase 3.
> - ⚠️ **Fix:** companies like the findings, but their logs were hard to get or missed the
>   tool or document data. Spend 2 weeks on log connectors (common bot platforms,
>   LangChain/LlamaIndex callbacks), then rerun Phase 2.
> - ❌ **Stop:** most say "we knew" or "doesn't matter", or flags were mostly wrong on real
>   data. The problem is too small or we can't solve it well enough. Pivot to the action
>   firewall ([STRATEGY.md §7](STRATEGY.md)), reusing engine, SDK and API.

## Phase 3: first revenue (Dec 9 – Jan 19)

- Sell the **Answer Audit** at $750 / ₹50,000 to the companies from Gate A and to new
  leads. Use the free audits as case studies (with permission).
- Build the minimum of **Guard**:
  - a review page: list of flags; buttons for real / not real / fixed
  - a Slack or email alert for new flags
  - a weekly summary email
- The review buttons record labels, so precision gets measured on each customer's own data.
- Offer one audit customer a 1-month Guard pilot.

> **Gate B (Jan 19):**
> - ✅ **Go:** at least 1 paid audit **and** at least 1 Guard pilot running. Plan pricing,
>   then a hosted version, and raise or apply to accelerators with real numbers.
> - ❌ **Stop or rethink:** no one pays after seeing free results. Sit down and decide
>   between pivoting to the action firewall or pausing.

## Standing rules

- **Every number we say publicly is in docs/EVIDENCE.md, with how it was measured.** No
  rounding up, no "up to".
- **Read every flag before a customer sees it,** until our measured precision on real data
  is good enough to stop.
- **No new feature without a customer asking for it,** except the false-alarm work in
  Phase 1.
- **Write a session note in `docs/sessions/` after each working session** (what changed,
  why, how it was verified).
