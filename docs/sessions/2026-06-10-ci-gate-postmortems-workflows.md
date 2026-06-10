# Session Log: 2026-06-10 (3) - CI Prompt Gate, Auto-Postmortems, Usage Workflows

## Scope

Brainstormed adoption-forcing features ("what makes an outside developer actually need this?"), built the two best on feature branches, merged them to main, and documented full usage workflows so anyone can wire Cassandra into their stack.

## The reasoning

The demo loop is strong but nothing pulled an outside developer into daily use. Two hooks fix that:

1. **Prompts are code, so test them like code.** Teams edit system prompts with zero regression testing. A CI gate that fails the build when a prompt edit drops the eval pass rate is a daily habit, not a demo.
2. **Incidents should arrive as postmortems, not bug reports.** Every supervision cycle already contains everything an on-call engineer writes by hand after an AI incident; rendering it as markdown makes the output land directly in existing processes (GitHub issues, Slack).

The flywheel that ties them together: a production failure -> Cassandra synthesizes a dataset -> the dataset becomes a CI gate suite -> that class of failure can never ship again. Failures compound into protection.

## Branch 1: feature/ci-prompt-gate (merged)

- `cassandra/gate.py`: `run_gate(prompt, cases, threshold, endpoint)` runs each case through the live agent (`system_override` + `session_id="test"` + replay auth headers) and judges with the Evaluator's `_JUDGE` prompt (single source of truth). Returns `GateResult` with per-case pass/why and a serialized `passed` computed field.
- New console script **`cassandra-gate`** (pyproject): `--prompt-file --cases --threshold --endpoint --max-cases --json`; exits 0/1 for CI.
- New MCP tool **`gate_prompt(prompt, cases, threshold)`** on `cassandra-mcp`.
- `examples/github-actions-prompt-gate.yml` (copy-paste CI workflow) + `examples/gate_cases.json` (dataset format = Synthesizer output shape).
- `tests/test_gate.py`: 4 offline tests (agent + judge monkeypatched), including CLI exit codes.

## Branch 2: feature/incident-postmortems (merged)

- `cassandra/report.py`: `render_postmortem(Incident) -> str`, a pure function (no LLM, no I/O) rendering: header (severity, diagnosis, confidence), what happened (input, bad answer, rationale), root cause (culprit, numbered causal chain, fix strategy), evaluation table (baseline vs candidate pass rates + cost/latency deltas), prompt diff block, replay before/after with FIXED verdict, red-team table, next-steps checklist. Contains no em dashes by design.
- `SupervisionPipeline.run_once()` writes `reports/<incident_id>.md` after the red-team stage (best-effort; an OSError cannot kill the loop). `reports/` gitignored.
- `supervise_latest` MCP tool now returns the markdown in a `postmortem` field.
- `tests/test_report.py`: 3 offline tests (full incident sections, bare incident omits optional sections, pipeline writes the file).

## Docs

- New `docs/WORKFLOWS.md`: four adoption-ordered workflows (IDE copilot via MCP with example prompts to type, CI gate, continuous live supervision, on-call postmortems) plus prerequisites for supervising YOUR agent (OpenInference spans + a `/chat` with gated `system_override`) and the one-paragraph adoption story.
- README: MCP table gains `gate_prompt` and the postmortem note, concrete per-tool use cases, new "CI prompt regression gate" and "Auto-postmortems" sections, repo layout + status table updated (6 MCP tools).
- `cassandra/mcp_server.py` module docstring updated with the full 6-tool list.

## Verification

- Full suite: 33 tests passing offline; `ruff check .` clean.
- Branches `feature/ci-prompt-gate` and `feature/incident-postmortems` pushed; both merged into main with `--no-ff` merge commits; main pushed.

## Open items (unchanged)

- GCP secrets + Cloud Build deploy, Agent Engine run, demo video.
