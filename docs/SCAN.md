# Scan your bot's logs in 5 minutes

`cassandra scan` reads exported chat logs and tells you which answers stated a specific fact (an amount, a temperature, a date…) that no tool call in that turn backed.

- **Nothing changes on your side.** No SDK, no Phoenix, no endpoint to expose.
- **Nothing leaves your machine** in the default mode. It's a rule check with no LLM.

```bash
pip install cassandra-ai
cassandra scan logs.jsonl --spec spec.json
# -> 8 of 50 answers stated a fact no tool backed (9 not checkable). Report: scan_report.md
```

## 1. Export your logs (one turn per line)

```json
{"id": "t1", "question": "What's the wire fee?", "answer": "The wire fee is $25.", "tool_calls": [{"name": "get_fee_schedule", "args": {"product": "wire"}, "result": {"found": false}}]}
```

| Field | Required | Also accepted as |
|---|---|---|
| `answer` | yes | `output`, `reply`, `response` |
| `question` | recommended | `input`, `user`, `message` |
| `tool_calls` | recommended, the evidence | `tools` |
| `id` | optional (defaults to the line number) | |

Each `tool_calls` entry is `{"name", "args", "result"}`, where `result` is what the tool actually returned. Without tool calls, every specific claim counts as unsupported, which is still useful: it shows what the bot says from memory.

**Where to get this:**
- **OpenAI / Anthropic tool calling:** you already log the messages. Map the user message to `question`, the final assistant text to `answer`, and each tool call plus its tool-result message to `tool_calls`.
- **LangChain / LangGraph:** take the run's input, final output and intermediate tool steps.
- **Phoenix / OpenTelemetry traces:** export the spans; root span input/output are the question and answer, child tool spans are the tool calls.
- **Plain database of chats:** a short script that writes one JSON object per line.

## 2. Write the spec (about 15 minutes)

The spec tells Cassandra which kinds of fact must come from which tool. Here's a 20-line example for a travel bot ([poc/travelpal/grounding_spec.json](../poc/travelpal/grounding_spec.json)):

```json
{
  "lookups": [
    { "tool": "convert_currency", "claims": ["money"], "success_key": "found" },
    { "tool": "get_weather", "claims": ["temperature", "precip_pct"], "success_key": "found" }
  ],
  "decline_markers": ["couldn't", "unable to", "can't provide", "not available"],
  "claim_extractors": {
    "money": "(?:[$€£¥₹]\\s?\\d[\\d,]*(?:\\.\\d+)?|\\b\\d[\\d,]*(?:\\.\\d+)?\\s*(?:[A-Z]{3}\\b|(?i:dollars?|euros?|rupees?|yen)\\b))",
    "temperature": "-?\\d+(?:\\.\\d+)?\\s*°\\s*[CF]",
    "precip_pct": "(?i)\\d+%\\s*(?:chance|probability)"
  }
}
```

- **`claim_extractors`:** a regex per kind of fact your bot states.
- **`lookups`:** which tool must have succeeded for that kind of fact. `success_key` is the field in the tool's result that is `true` on success.
- **`decline_markers`:** phrases your bot uses when it honestly can't answer.

Every key in `claim_extractors` must appear in some lookup's `claims` (or `fields`). Otherwise those answers are reported as *not checkable* rather than guessed.

**Rule of thumb:** write the spec *before* you read the report. Tuning it to the answers you've already seen flatters the numbers.

## 3. Read the report

`scan_report.md` gives a headline number, a breakdown, and up to 10 examples. Each example names the claim and the missing or failed tool call:

```
### 3. `h042` — How much is a SIM card in Japan?
> …you can expect to pay between 3,000 to 10,000 yen…
- Claim: `10,000 yen`
- Why: Answer asserts money ('10,000 yen') but convert_currency was never called.
```

| Result | Meaning |
|---|---|
| Unsupported fact | A specific claim with no successful matching tool call. Unverified, not necessarily false. |
| Backed by a tool result | Every claim had a successful matching call. |
| Honest decline | No claim, and the bot said it couldn't answer. |
| Not checkable | No claim the spec recognises. Add an extractor, or use `--judge`. |

## Options

| Flag | Does |
|---|---|
| `--spec spec.json` | Your grounding spec (or set `GROUNDING_SPEC_FILE`) |
| `--out report.md` | Report path (default `scan_report.md`) |
| `--json results.json` | Also write per-turn verdicts |
| `--top N` | Examples in the report (default 10) |
| `--judge` | Send *only* not-checkable turns to the LLM judge. Calls your configured LLM, so those turns leave the machine. |

## Known limits

- The rule checks that a matching tool call **succeeded**, not that it answered the **right question**. A weather result for the wrong city, or a forecast for the wrong day, counts as backed. Our test bot's wrong-city and wrong-weekday answers were missed for this reason.
- An amount repeated from the user's own question ("convert **1000 INR**") counts as a claim. It shows up as unsupported if that tool call failed.

## Measured accuracy

On 50 unseen questions to a real agent, with the spec written beforehand ([poc/travelpal](../poc/travelpal/README.md)):
- **Rule only:** 8 flagged, 8 really unsupported, 0 false alarms.
- **With `--judge`:** 11 flagged, 11 real, 0 false alarms.
- **Missed:** 4 of 15 bad answers, all wrong-date or wrong-city.
