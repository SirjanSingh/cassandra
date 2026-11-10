# RAGTruth: Cassandra's judge vs. human labels

**Question:** Do modern models still make things up when given the right documents? And can
Cassandra's LLM judge catch it when graded against labels written by *other people*, not by us?

**Data:** [RAGTruth](https://github.com/ParticleMedia/RAGTruth) (ACL 2024), ~18k answers from
six LLMs on three RAG tasks, with every span the source doesn't support marked by human
annotators. The data isn't committed. Download the two files into `data/`; the commands are
in the docstring of `run_claims.py`.

## 1. How often models go wrong *with* the right documents (all 17,790 answers)

Share of answers containing at least one unsupported or contradicting statement:

| Model | Q&A over passages | News summary | Data → text (business JSON) | All |
|---|---|---|---|---|
| GPT-4 (0613) | 4.2% | 7.8% | 28.1% | 13.7% |
| GPT-3.5 (0613) | 7.6% | 5.7% | 26.3% | 13.5% |
| Llama-2-70B | 32.4% | 22.5% | 83.5% | 47.0% |
| Mistral-7B | 38.2% | 65.4% | 92.7% | 65.9% |

**What this shows:**
- With good documents and a strong model, plain Q&A is mostly fine (about 4%).
- Turning structured data into prose (the closest task to "a tool returned JSON, the bot
  explains it") goes wrong about a quarter of the time, even for GPT-4.

**Caveat:** these are 2023 models. Current models are likely better. The same dataset has
no newer ones.

## 2. Can Cassandra's judge catch them?

`Diagnostician.judge` was used unchanged. The retrieved document was passed as the result of
a `retrieve_documents` tool call. Test split, GPT-4 and GPT-3.5 answers only.

| Judge model | Answers | Bad (human) | Caught | Missed | False alarms on good answers |
|---|---|---|---|---|---|
| gpt-4o-mini (shipped default) | 900 (all) | 88 | **8 (9%)** | 80 | 39 of 812 (4.8%) |
| gpt-4o-mini | 250 sample* | 88 | 8 (9%) | 80 | 7 of 162 (4.3%) |
| gpt-4o | 250 sample* | 88 | **13 (15%)** | 75 | 4 of 162 (2.5%) |

\* All 88 bad answers plus a fixed random 162 of the good ones (seed 0). Same rows for both
judge models.

**Verdict: Cassandra's judge is not a fine-grained fact-checker.**
- It rarely raises false alarms, but it misses most errors.
- The errors it misses are one wrong detail inside a long, otherwise correct answer, for
  example "his wife" where the article said someone else.
- It reads the answer as a whole, sees that it broadly matches the document, and says `ok`.

A bigger judge model helps a little: from 9% to 15% caught.

**What was *not* tested here:**
- Cassandra's deterministic rule (Layer 1). It needs tool calls and a grounding spec; RAG
  passages have neither.
- Any prompt tuning. The judge's prompt is written for tool-using support bots. Tuning it
  on this test split would make the numbers meaningless, so that would need the train split.

## 3. Improved: claim-by-claim checking (`cassandra/faithfulness.py`)

Two new checks, built after looking at the judge's misses:
- **`value_check`** (no LLM): every clock time and number in the answer must appear in the
  source.
- **`claim_check`** (LLM): split the answer into single facts and check each against the
  source. Missing or null data counts as unknown, not "no"; advice and opinion never count
  as failures.

**Method:**
- Prompt developed on the **train** split (300 answers, 50 bad + 50 good per task).
- One tuning round, which cut false alarms 18% → 14% and caught 46% → 41%.
- Then frozen and run **once** on the same 900 test answers as section 2, with gpt-4o-mini.

| Detector (gpt-4o-mini) | Caught (of 88 bad) | False alarms (of 812 good) | Flags that are real |
|---|---|---|---|
| Old whole-answer judge | 8 (9%) | 39 (4.8%) | 17% |
| `value_check` only | 6 (7%) | 14 (1.7%) | 30% |
| **`claim_check`** | **38 (43%)** | 121 (14.9%) | **24%** |
| either | 41 (47%) | 130 (16.0%) | 24% |

`value_check` rows are after the 2026-11-10 fixes (dates, rounding, numbers echoed from the
question); before them it was 8 caught / 16 false alarms. `claim_check` is unchanged.

Data → text, where 72 of the 88 errors are: `claim_check` caught 32 of 72 (44%), with 23%
false alarms.

**What this means:**
- **Recall:** checking claim by claim catches about **5× more** bad answers than the old
  judge (9% → 43%).
- **Precision:** a flag is also more likely to be real (17% → 24%).
- **Still noisy.** Only ~10% of answers are bad, so about 3 of every 4 flags are false
  alarms. Use it to build a human review queue, not to block answers automatically.
- **Possible label gaps.** Some "false alarms" on train were real errors the annotators
  missed, for example "preheat to 450°F" when the source says 250°F. They are still counted
  as false alarms; we did not relabel anything.
- **`value_check` is cheap and quiet** but rarely fires, because most errors here are
  yes/no attribute claims ("no WiFi") rather than numbers.

**Not yet tried:**
- gpt-4o or a reasoning model as the claim checker.
- A second pass that re-checks only the flagged claims to cut false alarms.

## Reproduce

Section 2's whole-answer judge (`run_judge.py`, `Diagnostician`) was removed with the old
pipeline on the `focus/answer-check` branch; its saved verdicts (`verdicts*.jsonl`,
`results*.json`) stay here as the baseline. The script lives on `feature/nli-and-hindi`.

```bash
python -m poc.ragtruth.run_claims --split train --per-task 50 --out claims_train_v2.jsonl   # tuning
python -m poc.ragtruth.run_claims --split test --out claims_test.jsonl                      # final
```

`claims_train_v1.jsonl` is the run before the one tuning round, kept for the record.

`--judge-model` exists because exporting `OPENAI_MODEL` in the shell does **not** work:
`cassandra/config.py` calls `load_dotenv(override=True)`, so `.env` wins.
