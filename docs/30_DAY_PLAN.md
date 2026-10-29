# 30-day plan (Oct 29 – Nov 28, 2026)

**Goal of the month:** find out whether real teams care that their bot makes things up.
Code only gets built if it helps answer that.

**Done means:** 3 real bots scanned, 3 reactions written down, and a clear keep-going-or-stop decision.

---

## Week 1 (Oct 29 – Nov 4): clean up and finish the proof

- [ ] Commit the TravelPal proof of concept (`poc/travelpal/`)
- [ ] Fix the judge: tell it today's date
- [ ] Fix the judge: an honest "I couldn't get that data" counts as OK
- [ ] Write a second set of ~50 TravelPal questions, without looking at the agent's answers first
- [ ] Run the full fix loop on TravelPal: diagnose → patch the prompt → re-score both question sets
- [ ] Write down the real before/after numbers (replaces the "illustrative" ones)
- [ ] One-page positioning note: what it is, who buys it, what it is not

## Week 2 (Nov 5 – Nov 11): make it easy to try on someone else's bot

- [ ] Build `cassandra scan logs.jsonl`: reads exported chat logs, no Phoenix needed
  - [ ] Input: one line per turn, `{question, answer, tool_calls}`
  - [ ] Output: a one-page report with "X% of answers stated facts with no source" and the worst 10 examples
- [ ] A 5-minute guide: "how to export your logs in this format"
- [ ] List 20 people or teams running a support or tool-using bot (college projects, startups, friends)
- [ ] Message 10 of them: "Free: I'll check your bot's answers for made-up facts"

## Week 3 (Nov 12 – Nov 18): run it on real bots

- [ ] Get logs from at least 2–3 bots
- [ ] Write a grounding spec for each one (about an hour per bot)
- [ ] Run the scan, then hand-check the flagged answers so you know the report is right
- [ ] Send each team its report
- [ ] Write down exactly what each team says (word for word if you can)

## Week 4 (Nov 19 – Nov 25): decide

- [ ] For each team: did they want it run again? Did they ask how to keep it running?
- [ ] Ask the most interested team for a small paid pilot
- [ ] Decide:
  - **People reacted ("how do we keep watching this?")** → build continuous monitoring next
  - **People shrugged** → stop adding features and rethink who it's for
- [ ] Write the decision and the evidence in `docs/sessions/`

---

## Realistically achievable in a month

- A tested scanner anyone can run on exported logs
- A proven fix loop with real before/after numbers on an honest agent
- Reports on 2–3 real bots
- Real feedback, and maybe one paid pilot

## Not realistic this month (don't start these)

- A hosted SaaS dashboard, logins, billing, multi-tenant setup
- Enterprise self-hosted packaging or security compliance
- Automatic prompt changes in production
- New detectors (wrong-place / entity checks) before a customer asks for them
- More demo agents or languages
