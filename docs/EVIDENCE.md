# Evidence: every number, how it was measured, and its caveats

Rule: if a number goes in a pitch, it comes from this page, with its caveat.

## 1. RAGTruth: the main benchmark (human labels, not ours)

Data: [RAGTruth](https://github.com/ParticleMedia/RAGTruth) (ACL 2024), ~18k answers from
six LLMs on three tasks (Q&A over passages, news summary, data → text from business JSON).
Human annotators marked every statement the source didn't support. Scripts and raw results
are in [poc/ragtruth/](../poc/ragtruth/README.md).

### How often models slip with the right documents (all 17,790 answers)

| Model | Q&A | Summary | Data → text | All |
|---|---|---|---|---|
| GPT-4 (0613) | 4.2% | 7.8% | 28.1% | 13.7% |
| GPT-3.5 (0613) | 7.6% | 5.7% | 26.3% | 13.5% |
| Llama-2-70B | 32.4% | 22.5% | 83.5% | 47.0% |

*Caveat:* these are 2023 models. Current models are likely better. The dataset has no newer ones.

### How well Cassandra catches them

Test split, GPT-4 and GPT-3.5 answers: 900 answers, of which 88 are bad by human label.
The claim-check prompt was developed on the **train** split, tuned once, frozen, then run
**once** on test. Checker model: gpt-4o-mini.

| Detector | Caught (of 88) | False alarms (of 812 good) | Flags that are real |
|---|---|---|---|
| Whole-answer LLM judge (old pipeline) | 8 (9%) | 39 (4.8%) | 17% |
| Numbers & times (`value_check`) | 6 (7%) | 14 (1.7%) | 30% |
| **Claim by claim (`claim_check`)** | **38 (43%)** | 121 (14.9%) | **24%** |
| Either | 41 (47%) | 130 (16.0%) | 24% |

On data → text, which holds 72 of the 88 errors: the claim check caught 32 (44%), with 23% false alarms.

*Caveats:*
- About 3 in 4 flags are false alarms, because only ~10% of answers are bad. Sell it as a
  review queue.
- Some "false alarms" on train were real errors the annotators missed (e.g. "preheat to
  450°F" when the source says 250°F). We counted them as false alarms anyway and relabelled
  nothing.
- The tool-call rule wasn't tested here (RAGTruth has no tool calls).
- With gpt-4o, the *old* judge went from 9% to 15% on a 250-answer sample. The claim check
  hasn't been run with gpt-4o yet.

## 2. TravelPal: a real tool-using bot (our labels)

A gpt-4o-mini travel assistant with live currency and weather APIs, nothing rigged. Details
in [poc/travelpal/README.md](../poc/travelpal/README.md). Its 50 held-out answers ship as
`cassandra demo`'s sample.

**Bad-answer rate:**
- Baseline prompt: 30% of held-out answers bad.
- After one prompt fix: 6% bad, with nothing useful refused.

**What Cassandra v0.4 catches on the 50 held-out answers** (15 labelled bad):

| Mode | Flagged | Truly bad | False alarms |
|---|---|---|---|
| Offline (rule + numbers) | 8 | 8 | 0 |
| With claim check (gpt-4o-mini) | 10 | 8 | 2 |

*Caveats:*
- The labels were written by us, on a single run each.
- 7 of the 15 bad answers are **wrong-entity or wrong-date** lookups (the geocoder picked
  the wrong city; dates were off). The bot faithfully reported data that was wrong for the
  question. Checking an answer against its data can't catch that, and no layer does.
- The bot never invented a tool result when a tool failed (0 of 22). The failures were
  quieter.

## 3. Numbers we do *not* have yet

- Precision or recall on any **real customer's** logs. This is what Phase 2 of the roadmap
  produces.
- Results with a stronger checker model or a second verification pass.
- Speed and cost at volume. Estimated at roughly $0.5–1 per 1,000 answers on gpt-4o-mini;
  not measured on a bill.
