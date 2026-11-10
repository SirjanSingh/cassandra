# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## Session protocol (keep the project's memory)

1. **At session start**, skim the newest file in `docs/sessions/` and this file.
2. **After each behavior-changing task**, update `docs/sessions/<YYYY-MM-DD>-<topic>.md`:
   what changed, why, files touched, how it was verified.
3. **At session end**, make sure docs whose behavior changed are updated (`README.md`,
   `docs/ARCHITECTURE.md`, `docs/EVIDENCE.md` for any accuracy change).
4. Settings are cached: `get_settings()` → call `reload_settings()` in scripts/tests after
   changing the environment.

## What this is

**Cassandra checks an AI bot's answers against the data the bot was given** (tool results
and/or retrieved documents) and flags statements that data doesn't back. Open source
(Apache-2.0), sold as done-for-you audits and a live "Guard" subscription. See
`docs/STRATEGY.md` (who, why, pricing) and `docs/ROADMAP.md` (the plan and its gates).

This branch (`focus/answer-check`, v0.4.0) is a deliberate cut-down of the earlier
multi-agent Phoenix pipeline, which lives on `feature/nli-and-hindi`. Don't reintroduce
pipeline pieces without a customer asking.

## Commands

```bash
pip install -e ".[dev]"
pytest                     # offline; the LLM is always mocked
ruff check .               # line length 100
mypy cassandra

cassandra demo             # bundled sample, offline
cassandra scan logs.jsonl [--spec spec.json] [--llm] [--out r.html|r.md] [--json r.json] [--fail-over PCT]
cassandra serve [--port 8090] [--spec spec.json]
python -m poc.ragtruth.run_claims --split train|test --out ...   # accuracy benchmark (costs API calls)
```

## Architecture (see docs/ARCHITECTURE.md)

`Turn` → `engine.check_turn` → three layers, cheapest first → `TurnResult` (verdict + findings):
1. **rule** (`grounding.py`): per-bot spec; a fact type with no successful tool call. Pure.
2. **value** (`faithfulness.value_check`): numbers and times must occur in the source. Pure.
3. **claim** (`faithfulness.claim_check`): LLM, claim by claim. The only network call.

Ways in: `scan.py` (JSONL), `cassandra.check()` (SDK), `server.py` (HTTP). Way out: `report.py`.

## Rules

- **All LLM calls go through `llm.structured()`.** OpenAI SDK, any OpenAI-compatible base URL.
- **All env access goes through `config.get_settings()`.** Real env vars beat `.env`.
- **The offline layers stay pure:** no network, env or LLM.
- **"Unchecked" is never "ok":** no logged source means nothing was checked.
- **Accuracy changes need the benchmark.** Editing `_CLAIM_SYSTEM`, the request in
  `llm.py` or `value_check` changes measured accuracy. Tune on RAGTruth *train*, report on
  *test* once, and update `docs/EVIDENCE.md` honestly.
- **Core install = pydantic only.** `openai` (`[llm]`) and `fastapi`/`uvicorn` (`[serve]`)
  are optional; import them lazily.
- **Never claim a number that isn't in `docs/EVIDENCE.md`.**
