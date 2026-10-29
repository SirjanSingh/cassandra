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

---

## Week 1 follow-up (run 2026-10-29): judge fix, held-out set, real fix loop

```bash
python -m poc.travelpal.fix_loop                       # diagnose -> root cause -> patch (q090)
python -m poc.travelpal.collect --questions questions_heldout.json --out runs_heldout.jsonl
python -m poc.travelpal.collect --questions questions_heldout.json --out runs_heldout_candidate.jsonl --system-file candidate_prompt.txt
python -m poc.travelpal.collect --out runs_candidate.jsonl --system-file candidate_prompt.txt
python -m poc.travelpal.score --runs runs_heldout.jsonl --labels labels_heldout.json --out results_heldout.json
```

### 1. Judge fixes (`cassandra/diagnostician.py`)

The judge is now told today's date, and the prompt says a plain "I couldn't retrieve that" counts as honest.

- **Judge alone:** false alarms 19 → 9, precision 37% → 53%.
- **Cascade:** 82% → 75%, from one extra false alarm. The judge called a reasonable "how to compare Wise with your bank" answer prompt drift.

### 2. Held-out set: the fair detection number

These are 50 new questions ([questions_heldout.json](questions_heldout.json)), written before running anything. The grounding spec was **frozen**, so nothing was tuned to these answers.

| Detector | Precision | Recall |
|---|---|---|
| Rule alone | 100% (8/8) | 80% of decided turns |
| **Cascade** | **100% (11/11)** | **73% (11/15)** |

The 4 misses are the same blind spot as before: three wrong-date answers ("Sunday" fetched for a Friday) and one wrong place (Calcutta, South Africa).

### 3. The fix loop, run for real

Cassandra's real stages ran on the q090 visa incident: `Diagnostician.judge → RootCauseAnalyst → Patcher`. Only the Phoenix write was stubbed ([fix_loop.py](fix_loop.py)). Details are in [fix_loop.json](fix_loop.json).

- **Root cause:** "fabricated visa cost; no tool results."
- **Fix strategy:** "mandatory tool check for visa-related queries."
- **The patch** ([candidate_prompt.txt](candidate_prompt.txt)) is narrowly worded, because it only saw one incident:
  > For any inquiries related to visa costs, you must check the relevant tool… If the required tool data is missing, inform the user that you cannot provide that information.

Both question sets were rerun with that prompt (via `system_override`) and hand-labelled again:

| | Baseline prompt | Cassandra's candidate | Cassandra's own measurement (cascade flags) |
|---|---|---|---|
| **Held-out (50)** | 15 bad (30%) | **3 bad (6%)** | 11 → 1 |
| Original (98) | 14 bad (14%) | 8 bad (8%) | 12 → 5 |
| Answerable questions still answered (both sets) | 63/63 | 63/63 | — |

By failure type, across both sets:

| Failure type | Before | After |
|---|---|---|
| Answered from memory | 20 | 4 |
| Wrong place | 4 | 3 |
| Misreported data / wrong date | 5 | 4 |

### What week 1 proves

- **The loop works end to end on a real agent.** One incident in, one prompt patch out. That patch cut bad answers on *unseen* questions from 30% to 6%, without making the bot refuse things it can answer.
- **The prompt fix only helps the class Cassandra can detect.** Answering from memory dropped about 80%. Wrong place and wrong date barely moved. Those need code or tool fixes, such as checking the geocoder's country or computing weekdays in a tool, not a prompt fix.
- **Cassandra under-reports its own improvement a little.** It counted 11 → 1 where the truth was 15 → 3. It can't see the wrong-date and wrong-place failures before or after, so its before/after is honest for what it can see, and blind to the rest.
- **The patch generalised by luck of wording.** The visa-only instruction carried a general sentence ("if tool data is missing, say so") that did the real work. Patching from a *cluster* of similar incidents instead of one would make this reliable, not lucky.
- **Caveats:** one run of each set (LLM output varies run to run), live weather changes between runs, and the labels are still mine alone.
