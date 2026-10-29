# TravelPal: proof of concept on an honest, real agent

**Question:** does Cassandra catch the bad answers of an agent nobody rigged?

ShopBot (`patient/`) is a demo. Its prompt tells it to never admit ignorance, and its tools fail on cue.
TravelPal is the opposite:

- **Ordinary prompt.** "You are TravelPal, a friendly assistant… use the tools." It neither forbids nor encourages guessing.
- **Real APIs.** [Frankfurter](https://frankfurter.dev) (ECB rates) and [Open-Meteo](https://open-meteo.com) (geocoding + 16-day forecast). Every failure is genuine:
  - ECB doesn't publish PKR/AED/NGN/…
  - forecasts stop 16 days out
  - the geocoder picks the wrong "Goa" (it returns Genoa, Italy).
- **Real model.** `gpt-4o-mini` answers. Cassandra judges with its configured LLM (`gpt-4o` in `.env`).
- **Real contract.** Questions go over HTTP through `cassandra.patient_client.ask_patient`, the same call Cassandra's stages make.
- **Labels first.** All 98 answers were hand-labelled ([labels.json](labels.json)) *before* any Cassandra verdict was looked at.

```bash
uvicorn poc.travelpal.agent:app --port 8090   # 1. the agent
python -m poc.travelpal.collect                # 2. 98 questions -> runs.jsonl
python -m poc.travelpal.score                  # 3. Cassandra vs hand labels -> results.json
```

The rule detector uses [grounding_spec.json](grounding_spec.json), which is 25 lines and the only per-agent config.

## Results (run 2026-10-29, 98 questions)

### What the agent actually got wrong: 14/98 (14%)

| Failure type | Count | Examples |
|---|---|---|
| Answered from memory, no tool behind it | 9 | Japan visa "₹6000–8000", Paris metro "€1.90" (outdated), a cash-carry limit that's wrong, Ladakh temps |
| Tool returned the **wrong place**, agent presented it as right | 3 | "Bombay, **United States**" for Bombay; "Bangalore" from Bangalore Town, **Pakistan**; "Kodagūr" passed off as Coorg |
| Real tool data, misreported | 2 | "This weekend" shown as Sat/Sun/Mon for dates that were Thu–Sat; "clear skies" that no tool returned |
| **Tool failed → model improvised** (the ShopBot failure) | **0 / 25** | Every unsupported-currency and out-of-range question was declined honestly |

### How Cassandra did

| Detector | Precision | Recall | Notes |
|---|---|---|---|
| **Rule alone** (deterministic, no LLM) | 88% (7/8) | 58% (7/12)* | Decides 85/98 turns, abstains on 13 |
| **LLM judge alone** (`Diagnostician.judge`) | **37%** (11/30) | 79% (11/14) | 19 false alarms, mostly honest declines flagged as "tool_failure" |
| **Cascade** (rule → LLM only on abstain), what ships | **82%** (9/11) | 64% (9/14) | Rule decided 85, LLM 13 |

\* recall over the bad answers among the turns the rule decided.

By failure type, the cascade caught:

- **answered from memory: 9/9**
- wrong place: 0/3
- misreported data: 0/2

## What this proves, and what it doesn't

**Proven.** On a real agent with a normal prompt, Cassandra catches every answer that states a specific fact no tool returned (9/9), with no LLM in the verdict for most of them. It cites the exact missing tool call. It does this with roughly 1 false alarm per 50 turns.

**Not proven, and worth knowing.**

1. **"Tool failed → model improvised" didn't happen.** A modern model with a plain prompt declined every time. The real failures are *answering beyond the tools* and *trusting a wrong tool result*. Pitch those.
2. **The rule only checks that *a* successful call exists.** It can't see that the call answered the wrong question (wrong city, wrong weekdays). That's the 5 misses, and the next detector to build (entity/argument checks).
3. **The LLM judge alone is not usable as an alarm.** 19 false alarms in 98 turns means paging someone one turn in five. It also has a real bug: it isn't told today's date, so it called correct 2026 dates "fabricated" (q016, q053).
4. **One rule false positive (q081).** The rule treats an amount *echoed from the user's question* ("1000 INR") as a claim.
5. Sample size is small: 98 turns, 14 positives. Treat the percentages as directional, not as benchmarks.
