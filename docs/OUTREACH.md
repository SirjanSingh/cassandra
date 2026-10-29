# Outreach kit: free scans for real bots

Week 2–3 of [30_DAY_PLAN.md](30_DAY_PLAN.md). The goal is 2–3 real bots scanned and their owners' reactions written down.

## Messages

### Short DM (LinkedIn, X, WhatsApp, Discord)

> Hey [name], saw you're building [bot/product]. Quick question: do you know how often it states a price, date or policy that none of its tools actually returned?
>
> I built a small open-source checker for exactly that. I ran it on a test travel bot, and 14–30% of answers had a made-up specific (visa fees, taxes, the wrong city), all sounding perfectly confident.
>
> Happy to run it on ~50 of your conversations for free and send you a one-page report. It works on exported logs, needs no code change, and runs on my machine with no LLM calls (or you can run it yourself). Interested?

### Email

> **Subject:** How often does [product]'s bot make things up?
>
> Hi [name],
>
> I'm building Cassandra, an open-source tool that checks AI agents' answers against their own tool calls. It flags any specific fact (amount, date, place, status) that no successful tool call backs up.
>
> On a test agent with a normal prompt and real APIs, 14–30% of answers contained an unbacked specific. None of them raised an error, and all of them sounded fine. After one automated prompt fix, the rate on unseen questions fell from 30% to 6%.
>
> I'd like to run it on your bot for free:
> - You send ~50 exported conversations (question, answer, tool calls). Redacted is fine.
> - I send back a one-page report: your percentage, plus the worst examples with the exact missing tool call.
> - It runs offline with no LLM, and the data is deleted afterwards. Or you run `pip install cassandra-ai` yourself and I'll help with the 15-minute setup.
>
> All I ask in return is 15 minutes of honest feedback on whether the report was useful.
>
> [your name]
> [GitHub link]

### Hinglish (friends, college, WhatsApp groups)

> Bhai, tumhare bot ke liye ek free check karna hai? Maine ek tool banaya hai jo pakadta hai jab bot koi price/date/policy bolta hai jo uske tools ne actually diya hi nahi. Mere test bot mein 14–30% answers mein aisa nikla, aur sab confident lag rahe the 😅
>
> Bas ~50 conversations ka log bhej do (question, answer, tool calls). Main ek page ki report bhej dunga. Data mere laptop pe hi rehta hai, koi LLM call nahi. Feedback chahiye bas.

### Follow-up (after 4–5 days with no reply, once only)

> Bumping this once. Even 20 conversations is enough for a first look. If it's not relevant, no worries at all.

## Who to send it to (aim for 20 names)

| Who | Where to find them | Why they're likely to say yes |
|---|---|---|
| Friends or classmates who built a bot with tools | Your network, college groups | Easiest yes; good practice run |
| Early startups with a support or booking bot (travel, fintech, edtech, D2C) | LinkedIn "AI agent" + "founder", Product Hunt, startup lists | They feel the pain and decide fast |
| People posting about LangChain / LangGraph / OpenAI-tool agents | X, LinkedIn, r/LangChain, Discord servers | Already logging tool calls |
| Indie hackers with AI chat products | Indie Hackers, X | Small, quick to respond |
| 2–3 bigger, regulated companies (fintech, insurance, health) | LinkedIn: "AI platform" / "conversational AI" leads | Strongest test of the target buyer |

Skip pure chit-chat bots and creative-writing apps. Cassandra needs bots that call tools and state checkable facts.

## When someone says yes

- [ ] Get the logs in the [SCAN.md](SCAN.md) format. Offer to write the conversion script yourself.
- [ ] Write their spec **before** reading their answers.
- [ ] Run `cassandra scan`, then hand-check every flagged answer before sending.
- [ ] Send the report and book 15 minutes.
- [ ] Ask:
  - "Did any of these surprise you?"
  - "Would you want this running every week? Who on your team would look at it?"
  - "What would you have to see to pay for this?"
- [ ] Write down their exact words right after the call.

## Tracker

| # | Name / team | Channel | Sent | Replied | Logs | Report sent | Reaction (their words) |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| 6 | | | | | | | |
| 7 | | | | | | | |
| 8 | | | | | | | |
| 9 | | | | | | | |
| 10 | | | | | | | |

**What to expect:** with cold messages, roughly 1–3 in 10 reply and maybe 1 sends logs, so start with friends and warm intros.

**Keep claims honest:** the numbers come from one test bot. Keep the wording "on a test agent", never "bots make things up 30% of the time".
