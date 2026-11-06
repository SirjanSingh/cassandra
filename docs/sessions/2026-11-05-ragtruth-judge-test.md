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

## Follow-up: claim-by-claim checker (`cassandra/faithfulness.py`)

- **Why:** the whole-answer judge misses single wrong details. 72 of the 88 test errors are
  data→text, mostly yes/no attribute claims ("no WiFi" when the field is null) and wrong hours.
- **What:**
  - `value_check`: deterministic, no LLM. Times and numbers in the answer must occur in the
    source. Fixed a bug where "9:00 PM" was also read as 09:00.
  - `claim_check`: an LLM splits the answer into atomic claims and checks each one.
    Null data counts as unknown; advice and opinion are never failures.
  - Neither is wired into the pipeline or `scan` yet.
- **Method:** developed on the train split (300 answers). One tuning round (advice and
  paraphrase are not failures), then frozen and run once on the 900 test answers.
- **Test result (gpt-4o-mini):** caught 38 of 88 (**43%**, the old judge caught 9%), with
  14.9% false alarms. 24% of flags are real (the old judge: 17%). That makes it a review
  queue, not an auto-blocker.
- **Files:** `cassandra/faithfulness.py`, `tests/test_faithfulness.py` (8 tests; the suite is
  124 passed), `poc/ragtruth/run_claims.py`, `claims_*.jsonl` + `_results.json`, and the
  README's section 3.

## Open items

- Try gpt-4o, or a second pass that re-checks only flagged claims, to cut false alarms.
  Tune on train only.
- Wire `claim_check` into `cassandra scan --judge` for turns whose tool results are logged.

- If the judge is to be pitched for RAG bots, try a claim-by-claim judge prompt, tuned on
  RAGTruth's train split and scored on test.
- Consider whether `load_dotenv(override=True)` should stop overriding real env vars. It
  surprises scripts and CI.
