# Session Log: 2026-11-05 — Cassandra's judge vs. RAGTruth human labels

Branch: `feature/nli-and-hindi`. Write-up: `poc/ragtruth/README.md`.

## Why

- The user doubted the pitch: "modern LLMs don't hallucinate", and "can't RAG replace us?".
- The TravelPal evidence used labels we wrote ourselves.
- No real company logs are available, so we tested on a public dataset labelled by humans:
  RAGTruth (ACL 2024, ~18k answers from 6 models with documents supplied).

## Results

- **Error rates with the right documents** (all 17,790 answers):
  - GPT-4 (0613) is wrong in 4.2% of Q&A, 7.8% of summaries and **28.1% of data→text**; 13.7% overall.
  - Llama/Mistral are 47–66% overall.
  - These are 2023 models, so current models are likely better.
- **Cassandra's judge, unchanged** (document passed as a `retrieve_documents` tool result):
  - gpt-4o-mini on 900 test answers caught **8 of 88** bad answers (9%), with 4.8% false alarms.
  - gpt-4o on a 250-answer sample caught **13 of 88** (15%), with 2.5% false alarms.
  - It misses single wrong details in long answers, so it is **not a fine-grained fact-checker**.
- Not tested: the deterministic rule (it needs tool calls and a spec), and any prompt tuning (that would need the train split).

## Gotcha found

`cassandra/config.py` calls `load_dotenv(override=True)`, so an `OPENAI_MODEL=...` shell
export is silently ignored when `.env` sets it. The first "gpt-4o" run was really
gpt-4o-mini; 94 of 250 rationales matched the mini run word for word, which exposed it.
`run_judge.py --judge-model` sets `get_settings().openai_model` directly instead.

## Files

- New: `poc/ragtruth/run_judge.py`, `README.md`, `verdicts*.jsonl`, `results*.json`.
- `.gitignore`: `poc/ragtruth/data/` (the dataset is 35 MB).

## Open items

- If the judge is to be pitched for RAG bots, try a claim-by-claim judge prompt, tuned on
  RAGTruth's train split and scored on test.
- Consider whether `load_dotenv(override=True)` should stop overriding real env vars. It
  surprises scripts and CI.
