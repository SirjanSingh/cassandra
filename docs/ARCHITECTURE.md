# Architecture

One job: take a bot turn (question, answer, and what the bot was given) and return a verdict
with findings. Everything else is a way in or a way out.

```
                  ┌──────────── ways in ─────────────┐
  exported logs ──► scan.load_turns ─┐
  Python code   ──► cassandra.check ─┼──► Turn ──► engine ──► TurnResult ──┬─► report.py (HTML / MD / JSON)
  HTTP request  ──► server /v1/check ┘                                     └─► API response / your code

  engine (engine.py), cheapest layer first:
     1. rule   grounding.py     needs a GroundingSpec      free, offline
     2. value  faithfulness.py  needs tool results/context free, offline
     3. claim  faithfulness.py  needs source + LLM         1 call → llm.py → any OpenAI-compatible API
```

## Modules (`cassandra/`)

| File | Responsibility | Depends on |
|---|---|---|
| `models.py` | Data shapes: `Turn` (in), `Finding`, `TurnResult`, `Report` (out). `Turn.source()` decides what the answer is checked against. | pydantic |
| `grounding.py` | **Rule layer.** Per-bot `GroundingSpec`: which fact types (regex) must be backed by a successful call to which tool. Abstains when unsure. | models |
| `faithfulness.py` | **Value layer** (`value_check`: numbers and times must occur in the source, allowing dates, rounding and numbers from the question) and **claim layer** (`claim_check`: LLM splits the answer into atomic claims and labels each `supported / contradicted / not_in_source / opinion`). | llm |
| `engine.py` | Runs the layers on one turn (`check_turn`, `check_offline`) or many with bounded concurrency (`check_many`) and turns findings into a verdict: `flagged / ok / declined / unchecked`. | the three layers |
| `llm.py` | The only LLM call site. OpenAI SDK against any OpenAI-compatible base URL. The request shape is what produced the benchmark numbers; change it, re-run the benchmark. | openai (optional) |
| `config.py` | All settings from the environment / `.env` (real env vars win). Cached; `reload_settings()` after changes. | pydantic-settings |
| `scan.py` | JSONL log loader with field aliases and line-numbered errors. | models |
| `report.py` | Self-contained HTML (no scripts, no external assets, dark mode, escaped), Markdown, JSON. | models |
| `server.py` | FastAPI app: `POST /v1/check`, `GET /health`, optional bearer key. | fastapi (optional) |
| `cli.py` | `cassandra demo / scan / serve`. Lazy imports, so `--help` is instant. | everything, lazily |
| `samples/` | 50 real answers from the TravelPal bot and its spec, for `cassandra demo`. | — |

**Packaging:** the core install is pydantic only (offline layers + CLI). The extras are
`[llm]` (openai), `[serve]` (fastapi, uvicorn), `[full]` = both, and `[dev]`.

## Rules to keep

1. **Every LLM call goes through `llm.structured()`.** One place to swap providers, add
   retries and log cost.
2. **The offline layers stay pure.** No network, no env, no LLM, so they are safe to run
   on any log.
3. **"Unchecked" is never "ok".** A turn with no logged tool results or context has nothing
   to check against and must say so.
4. **Changing `_CLAIM_SYSTEM`, `llm.py`'s request shape or `value_check` changes the
   product's measured accuracy.** Tune on RAGTruth *train*, report on *test* once
   (`poc/ragtruth/run_claims.py`), and update docs/EVIDENCE.md.
5. **The claim check announces itself.** The CLI prints which endpoint receives the data
   before sending anything.

## Deployment modes

| Mode | How | Data leaves the machine? |
|---|---|---|
| Batch audit | `cassandra scan logs.jsonl [--llm]` on a laptop | Only with `--llm`, to the configured endpoint |
| In-process | `await cassandra.check(...)` inside the bot | Only the claim check's LLM call |
| Sidecar | `cassandra serve` next to the bot; the bot POSTs each answer | Same; point `OPENAI_BASE_URL` at a local model for none at all |
| CI gate | `cassandra scan test_logs.jsonl --fail-over 5` | Same as batch |

## What's deliberately missing (and where it would go)

- **Review queue UI and alerts** (the Guard tier): a small web app over stored
  `TurnResult`s, where people mark flags real or not. The marks double as labels for
  measuring precision. New module `review/`; it doesn't touch the engine.
- **Second-pass verification** to cut false alarms: re-check only the flagged claims with
  a stronger model. Lives in `faithfulness.py` behind a setting.
- **Persistence:** none today. The scan writes files and the API is stateless.
