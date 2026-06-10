# Cassandra Workflows: How To Actually Use It

This page is for someone who wants to *use* Cassandra, not just demo it. Four workflows, ordered by how people typically adopt them: start with the IDE tools (zero infrastructure), add the CI gate (your first daily habit), then run live supervision, and let the postmortems land in your incident process.

The common thread: a production failure becomes a dataset, the dataset becomes a CI gate, and the gate prevents the failure from ever shipping again. Failures compound into protection.

## Prerequisites

```bash
pip install -e .
cp .env.example .env    # set OPENAI_API_KEY (or Gemini/Vertex), Phoenix URL + key
```

The bundled ShopBot in `patient/` is only the demo victim. Cassandra supervises **any** agent — see the next section for exactly what yours needs.

## Bring your own agent

Cassandra has two layers, with different integration costs:

| Capability | What your agent needs |
| --- | --- |
| **Passive**: watch traces, diagnose failures, root-cause, synthesize eval datasets, annotate spans | Nothing but OpenInference spans in a Phoenix project. Set `PATIENT_PROJECT` and you're done. |
| **Active** (the closed loop): score baseline vs candidate prompts live, replay the failing input, red-team the patch | The small HTTP contract below — about 30 lines of wrapper. |

### The active contract

All of Cassandra's live probes go through one module, `cassandra/patient_client.py`, so this is the entire contract:

```
POST {PATIENT_ENDPOINT}
  body:    {"message": str, "session_id": "test", "system_override": str?}
  headers: X-Cassandra-Token: <REPLAY_SHARED_SECRET>   (when configured)
  reply:   {"reply": str, "total_tokens": int, "latency_ms": int}
```

Plus two span attributes on the traces your agent exports: `patient.session_id` and `patient.prompt_variant` (`"candidate"` when a `system_override` was applied). They are what keeps Cassandra from supervising its own probe traffic.

**[`examples/adapter_template.py`](../examples/adapter_template.py)** is a ready-to-copy FastAPI wrapper that implements all of this — you fill in one function (`run_my_agent`) that calls your agent.

### Configuration for a non-ShopBot agent

```bash
PATIENT_PROJECT=my-agent-prod                 # the Phoenix project your agent traces into
PATIENT_ENDPOINT=http://my-agent:8082/chat    # your adapter endpoint (active layer)
PATIENT_PROMPT_NAME=my-agent-system           # Phoenix prompt name for patched versions
BASELINE_PROMPT_FILE=prompts/system_prompt.txt
REPLAY_SHARED_SECRET=<random>                 # same value on Cassandra and the adapter
```

`BASELINE_PROMPT_FILE` tells Cassandra what your agent's *current* system prompt is (the thing it diffs patches against). If you skip it, Cassandra tries to extract the system message from the failing trace itself (`llm.input_messages`), and only falls back to the bundled ShopBot prompt in demo mode — the resolution chain lives in `cassandra/baseline.py`.

## Workflow 1: IDE copilot (zero infrastructure)

Register `cassandra-mcp` in Claude Desktop, Claude Code, or Cursor and the supervision tools become part of your normal coding session. No Phoenix needed for the composable tools.

```json
{
  "mcpServers": {
    "cassandra": {
      "command": "cassandra-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-...",
        "PHOENIX_BASE_URL": "http://localhost:6006",
        "PHOENIX_API_KEY": "local",
        "PATIENT_ENDPOINT": "http://localhost:8082/chat"
      }
    }
  }
}
```

Real prompts you can type at your assistant once it is registered:

- "Here is a customer message and my agent's reply. **Diagnose** whether it hallucinated." (`diagnose`)
- "It fabricated a refund policy. **Generate 10 adversarial eval cases** that stress the same weakness." (`synthesize_evals`)
- "Here is my system prompt and the failure. **Propose a minimal patch** and show me the diff." (`propose_patch`)
- "**Gate my new prompt** against `evals/cases.json` at 80%." (`gate_prompt`)
- "**Supervise the latest production trace** and give me the postmortem." (`supervise_latest`)

That last one runs the full loop and returns paste-ready markdown you can drop into an issue.

## Workflow 2: CI prompt regression gate (the daily habit)

Prompts are code. When someone edits a system prompt, nothing in a normal CI run catches a behavioral regression. `cassandra-gate` does:

```bash
cassandra-gate \
  --prompt-file prompts/system_prompt.txt \
  --cases evals/cases.json \
  --threshold 0.8
```

Exit code 0 when the pass rate clears the threshold, 1 when it does not, so it slots into any CI. A ready-to-copy GitHub Actions workflow is in [`examples/github-actions-prompt-gate.yml`](../examples/github-actions-prompt-gate.yml), and [`examples/gate_cases.json`](../examples/gate_cases.json) shows the dataset format:

```json
[{"input_text": "...", "expected_answer": "...", "acceptance_criterion": "..."}]
```

This is the same shape Cassandra's Synthesizer emits. So the flywheel is:

```
production failure -> Cassandra synthesizes a dataset -> commit it to evals/
                   -> every future prompt PR is gated against it
```

Each case runs through your live agent (staging endpoint) under the prompt being tested, and the answer is judged by the same LLM-as-judge the Evaluator uses.

## Workflow 3: Continuous live supervision

The full loop, running unattended against production traces:

```bash
uvicorn patient.agent:app --port 8082      # your agent (or the bundled ShopBot)
uvicorn dashboard.main:app --port 8085     # cockpit + in-process 10s supervision loop
```

The dashboard's background loop polls Phoenix, and for each fresh failing trace runs: diagnose, root-cause, synthesize, evaluate baseline, patch, evaluate candidate, replay the original input, red-team the fix. Everything streams live to the cockpit at `http://localhost:8085`, and every artifact (annotation, dataset, prompt version) is written back into Phoenix.

One-shot instead of continuous: `python scripts/run_pipeline.py` drives exactly one end-to-end cycle, which is also the demo path.

For cloud deployment (Cloud Run + Secret Manager + Firestore state), use `deploy/cloudbuild.yaml`; see the deploy checklist in the session notes.

## Workflow 4: On-call postmortems

Every completed cycle writes `reports/<incident_id>.md`: a full postmortem with the diagnosis, severity, root cause chain, baseline vs candidate pass rates, the prompt diff, before/after replay evidence, and the red-team table, ending with a next-steps checklist.

Where it goes:

- File it as a GitHub issue: `gh issue create --title "AI incident" --body-file reports/inc-<id>.md`
- Paste it into the incident Slack channel.
- Attach it to the PR that applies the prompt patch, as the evidence for the change.

The `supervise_latest` MCP tool returns the same markdown in its `postmortem` field, so an agent can run supervision and file the issue in one breath.

## The adoption story in one paragraph

Day 1: register the MCP server and use `diagnose` and `propose_patch` ad hoc while building your agent. Week 1: commit your first eval dataset and add `cassandra-gate` to CI, so prompt PRs are now tested like code. Week 2: point the supervision loop at your Phoenix project, and incidents start arriving as postmortems with verified fixes instead of vague bug reports. Every incident makes the CI gate stricter. That is the whole point: the system gets harder to break the more it breaks.
