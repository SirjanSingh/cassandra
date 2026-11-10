# Outreach: finding the first 3 audits

Phase 1 of [ROADMAP.md](ROADMAP.md). The goal is 30 messages, 5 calls and 3 companies that
send logs. Who we're looking for is in [STRATEGY.md §3](STRATEGY.md).

## The qualifying question (ask it first)

> "When your bot answers, do your logs keep what it looked up: the API/tool results or the
> documents it retrieved?"

- **Yes:** a fit. Ask for logs.
- **"Only the chat":** we can't check much yet. Note them as a connector lead and move on.

## Messages

### Short DM (LinkedIn, X, WhatsApp)

> Hi [name], I saw [company]'s bot handles [orders/bookings/support]. Quick question: do you
> know how often it reads the right data and still tells a customer something slightly
> different, like the wrong date, wrong fee or wrong carrier?
>
> I built an open-source checker for exactly that. On a public benchmark with human labels it
> finds 43% of bad answers, where a standard AI judge finds 9%.
>
> I'm doing free audits for 3 companies: you send a few hundred exported conversations
> (with what the bot looked up), and I send back a report of every answer the data doesn't
> back, plus the top fixes. Worth a 15-min call?

### Email

> **Subject:** Answers your bot's own data doesn't back
>
> Hi [name],
>
> AI support bots rarely fail loudly now. The common failure is quieter: the bot looks up
> the right order or policy and then says something slightly different. On a public
> benchmark, even GPT-4 did this in about 1 in 4 answers when turning records into sentences.
>
> Cassandra (open source, `pip install cassandra-ai`) checks every answer against the tool
> results and documents the bot was given, and flags each statement that doesn't match.
>
> I'm running free audits for three companies this month:
> - You export a few hundred conversations, including tool results or retrieved text.
>   Redacted is fine.
> - Within 3 days I send an HTML report of every flagged answer, the 3 most common
>   patterns, and how to fix each.
> - Data stays on my machine or your chosen model endpoint and is deleted afterwards. Or run
>   it yourself and I'll help.
>
> In return: 15 minutes of honest feedback, and permission to quote the (anonymised) results.
>
> [name] · [GitHub link]

### Hinglish (warm network)

> Bhai, tumhare bot ka ek free audit karna hai? Mera tool check karta hai ki bot ne jo bola
> wo uske apne data (API result / documents) se match karta hai ya nahi: galat date, galat
> fee, galat carrier, sab pakadta hai. Kuch sau conversations ka export bhej do (jo bot ne
> lookup kiya wo bhi), 3 din mein report bhej dunga. Bas 15 min feedback chahiye.

### Follow-up (once, after 4–5 days)

> Bumping this once. Even 100 conversations is enough for a first look. No worries if it's
> not relevant.

## Where to find the 30

| Who | Where | Why |
|---|---|---|
| Friends or classmates with a bot that calls tools | Your network, college groups | Easiest yes; practice the audit |
| D2C / e-commerce brands with an order-status bot | LinkedIn ("head of CX", "support ops"), brand sites with chat widgets | A wrong delivery date or refund costs them directly |
| Travel, fintech, insurance startups with support bots | LinkedIn, startup lists, Product Hunt | Wrong fees or terms are costly and regulated |
| Engineers posting about LangChain / LlamaIndex / OpenAI tool agents | X, LinkedIn, Discord, r/LangChain | Already log tool calls, so easy logs |
| Agencies that build bots for clients | LinkedIn, Clutch | One yes can bring many bots |

## Running an audit (when someone says yes)

1. **Logs:** get their export, then write a converter to our JSONL (`question`, `answer`,
   `tool_calls` and/or `context`). Keep the converter in a private folder; it's the seed of
   a connector.
2. **Spec (optional):** if they use tools, write a small spec for the facts that must come
   from tools (prices, dates, statuses). Write it before reading their answers.
3. **Run:**
   ```bash
   cassandra scan their_logs.jsonl --llm --spec their_spec.json --json results.json
   ```
4. **Read every flag yourself.** Remove the clear false alarms from the report you send,
   but **record the count**: that's our real precision.
5. **Send:** the HTML report, plus a one-page note covering the share flagged, the top 3
   patterns with an example each, and the suggested fix (a prompt or data change).
6. **Call (30 min).** Ask:
   - "Which of these did you not know about?"
   - "Would you want this every week? Who would look at it?"
   - "What would make this worth paying for?"
7. **Write down their exact words** in the tracker right after.
8. **Delete their data** when done, and tell them it's deleted.

## Tracker

| # | Company | Contact / channel | Fits? (logs have tool data) | Sent | Replied | Call | Logs | Report | Flags real / total | Their words | Next step |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | | | | | | | | | | | |
| 2 | | | | | | | | | | | |
| 3 | | | | | | | | | | | |
| 4 | | | | | | | | | | | |
| 5 | | | | | | | | | | | |

## Keep claims honest

- Say "on a public benchmark with human labels" every time you quote 43%.
- Never say "your bot hallucinates X%". Say "X% of answers had a statement the data
  doesn't back, and we checked them by hand".
- If a report has few findings, say so. A clean bill of health is also a useful result,
  and it's honest.
