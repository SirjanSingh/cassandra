# RAGTruth: Cassandra's judge vs. human labels

**Question:** Do modern models still make things up when given the right documents? And can
Cassandra's LLM judge catch it when graded against labels written by *other people*, not by us?

**Data:** [RAGTruth](https://github.com/ParticleMedia/RAGTruth) (ACL 2024), ~18k answers from
six LLMs on three RAG tasks, with every span the source doesn't support marked by human
annotators. The data isn't committed. Download the two files into `data/`; the commands are
in the docstring of `run_judge.py`.

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

## Reproduce

```bash
python -m poc.ragtruth.run_judge                                   # 900, configured model
python -m poc.ragtruth.run_judge --sample 250 --judge-model gpt-4o --out verdicts_gpt4o_sample.jsonl
```

`--judge-model` exists because exporting `OPENAI_MODEL` in the shell does **not** work:
`cassandra/config.py` calls `load_dotenv(override=True)`, so `.env` wins.
