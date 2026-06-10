# 2026-06-11 — Decouple the pipeline from ShopBot (bring-your-own-agent)

## Scope / why

User question: "is the project hardcoded just for ShopBot so no one else can use it?"
Audit answer: the passive layer (Watcher → Diagnostician → RootCause → Synthesizer) and
the composable MCP tools / `cassandra-gate` were already generic, but the **closed loop
was hard-wired to ShopBot in two ways**:

1. `loop_agent.py` and `patcher.py` did `from patient.agent import FRAGILE_SYSTEM_PROMPT`
   — the pipeline imported the victim's *source code* to know the baseline prompt. A
   third-party agent has no module to import, so the loop could not run for anyone else.
2. `patcher.py` hardcoded the Phoenix prompt name `patient-shopbot-system`.

Decision: make the supervised agent a pure *configuration target* (P0), and formalize the
HTTP contract third parties implement as one module + a copyable adapter (P1). Demo
behavior is unchanged (ShopBot remains the zero-config fallback).

## Changes

- **`cassandra/baseline.py` (new)** — `resolve_baseline_prompt(span)` resolver chain:
  `BASELINE_PROMPT_FILE` env → the failing span's OpenInference `llm.input_messages`
  system message (handles nested list, JSON-string, and flat dotted-key shapes) →
  `patient.agent.FRAGILE_SYSTEM_PROMPT` if importable → `BaselinePromptError` with a
  clear remediation message. This is now the ONLY place `patient/` may be referenced
  from `cassandra/` (and only as an optional fallback import).
- **`cassandra/patient_client.py` (new)** — `ask_patient()`; the single gateway for all
  live probes to the supervised agent. Module docstring IS the integration contract
  (POST body, `X-Cassandra-Token` header, response shape, `session_id="test"` rule).
- **`cassandra/loop_agent.py`** — removed the `patient.agent` import; resolves the
  baseline once per incident and stores it on the new `Incident.baseline_prompt` field.
- **`cassandra/patcher.py`** — removed the `patient.agent` import; uses
  `inc.baseline_prompt` (resolver fallback when driven standalone); prompt name and
  Phoenix URL now come from `settings.patient_prompt_name`.
- **`cassandra/evaluator.py`, `replay.py`, `redteam.py`, `gate.py`** — all four
  hand-rolled `httpx.post` call sites replaced with `ask_patient()` (gate keeps the
  `_ask_agent(c, endpoint, message, prompt)` signature because tests monkeypatch it).
- **`cassandra/config.py`** — new settings `baseline_prompt_file: str | None` and
  `patient_prompt_name: str = "patient-shopbot-system"` (default preserves the demo's
  Phoenix prompt history).
- **`cassandra/models.py`** — `Incident.baseline_prompt: str | None`.
- **`examples/adapter_template.py` (new)** — ~120-line FastAPI wrapper a user copies to
  make their own agent supervisable: implements override gating (session_id + shared
  secret), the two feedback-loop span attributes, and the response shape; they fill in
  one `run_my_agent()` function.
- **Docs** — `docs/WORKFLOWS.md` gained a "Bring your own agent" section with a
  passive-vs-active capability table, the contract spec, and non-ShopBot env config;
  `.env.example` documents the two new vars; `CLAUDE.md` got a new convention bullet
  ("never import from `patient/` inside `cassandra/`; all probes via patient_client").

## Verification

- `pytest` — 39 passed (33 pre-existing + 6 new in `tests/test_baseline.py` covering
  file-wins, nested/JSON/flat span extraction, ShopBot fallback, and the error path via
  a `sys.modules["patient.agent"] = None` import block).
- `ruff check .` and `mypy cassandra patient dashboard` — clean (see session log).
- No behavior change for the demo: with no new env set, the resolver lands on the
  ShopBot fallback and the prompt name default matches the old hardcoded string.

## Notes / open items

- `.env` changes still require a server restart (`get_settings()` cached).
- Future (post-deadline) P3: multi-target supervision — turn
  `patient_endpoint`/`patient_project`/`patient_prompt_name` into a registry so one
  Cassandra instance supervises N agents.
- The default `patient_prompt_name` stays `patient-shopbot-system` deliberately so the
  demo's existing Phoenix prompt-version history remains continuous.
