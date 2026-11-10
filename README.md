# Cassandra

**Checks your AI bot's answers against the data it was given, and shows you every statement
that data doesn't back.**

Your support bot looks up an order and says *"it ships Friday via FedEx"*, but the order
system said UPS. Your RAG bot summarises a policy and adds a refund window the document
never mentions. The answers sound right, so nobody notices until a customer does.

Cassandra reads what the bot said next to what its tools and documents returned, and flags
the gaps.

```bash
pip install cassandra-ai
cassandra demo          # a report on 50 real answers from a sample bot, no setup
```

## What it checks

Three layers, cheapest first. Each runs only when it has what it needs.

| Layer | Catches | Cost |
|---|---|---|
| **Tool-call rule** | A fact type that must come from a tool (a price, a date) stated with no successful call to that tool | Free, offline. Needs a small spec |
| **Numbers & times** | A number or time in the answer that appears nowhere in the bot's data | Free, offline |
| **Claim by claim** | The answer split into single facts, each checked against the data: contradictions and invented details | One LLM call per answer (roughly $0.5–1 per 1,000 answers on gpt-4o-mini) |

**How well it works** (details in [docs/EVIDENCE.md](docs/EVIDENCE.md)):
- **RAGTruth** (public benchmark, human labels, 900 held-out answers): the claim-by-claim
  check caught **43%** of bad answers, against 9% for a whole-answer LLM judge. About
  **1 in 4 flags** was a real problem.
- So it is a **review queue that finds what humans would miss**, not an autopilot.

## Use it three ways

**1. Scan exported logs** (batch, offline by default):

```bash
cassandra scan logs.jsonl                 # free offline checks
cassandra scan logs.jsonl --llm           # + claim-by-claim (uses your LLM key)
cassandra scan logs.jsonl --spec spec.json --fail-over 5   # CI: exit 1 above 5% flagged
```

One JSON object per line. `tool_calls` and/or `context` are what the bot was given:

```json
{"id": "t1", "question": "Where is my order?", "answer": "It ships Friday via FedEx.",
 "tool_calls": [{"name": "lookup_order", "args": {"id": "A1"}, "result": {"carrier": "UPS"}}],
 "context": "optional: retrieved documents, as text, a list, or JSON"}
```

The output is a self-contained HTML report (or `--out report.md`) you can forward to anyone.

**2. In your code** (live, per answer):

```python
import cassandra
result = await cassandra.check(answer, question=q, tool_calls=calls, context=docs)
if result.verdict == "flagged":
    route_to_human(result.findings)
```

**3. As an HTTP service next to your bot** (`pip install "cassandra-ai[serve]"`):

```bash
CASSANDRA_API_KEY=... cassandra serve --port 8090
curl -X POST localhost:8090/v1/check -H "Authorization: Bearer ..." \
     -d '{"answer": "...", "tool_calls": [...], "context": "..."}'
```

## Setup for the claim check

```bash
pip install "cassandra-ai[llm]"
export OPENAI_API_KEY=sk-...                         # or any OpenAI-compatible endpoint:
export OPENAI_BASE_URL=http://localhost:11434/v1     # e.g. a local Ollama: data never leaves
export CASSANDRA_MODEL=gpt-4o-mini                   # the benchmarked default
```

The offline layers never send anything anywhere. The claim check sends each answer and its
data only to the endpoint you configure, and says so before it starts.

## Limits

- It only sees what was logged. If the tool results or documents aren't in the log, the
  answer is marked *no data to check*, not *ok*.
- It checks the answer against the data, not the data against the question. A bot that
  looked up the wrong city and reported it faithfully passes.
- Flags are "unverified", not "false". Expect false alarms, and review them.

## Project docs

- [docs/STRATEGY.md](docs/STRATEGY.md): who it's for, business model, pricing, competition
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the code fits together
- [docs/ROADMAP.md](docs/ROADMAP.md): the plan, with go/no-go gates
- [docs/EVIDENCE.md](docs/EVIDENCE.md): every number, how it was measured, and its caveats
- [docs/OUTREACH.md](docs/OUTREACH.md): how we find and onboard the first customers

Apache-2.0. The earlier multi-agent supervision pipeline (Phoenix, auto-patching, red-team)
lives on the `feature/nli-and-hindi` branch.
