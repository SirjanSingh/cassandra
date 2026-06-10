"""Drop-in adapter: make YOUR agent supervisable by Cassandra.

Cassandra's passive layer (diagnose / root-cause / synthesize) works on ANY agent
that exports OpenInference spans to Phoenix — no code changes. This template adds
the ACTIVE layer: the small HTTP contract that lets Cassandra also evaluate,
patch-test, replay, and red-team your agent live (the closed loop).

Copy this file, implement `run_my_agent()`, and run it next to your agent:

    uvicorn adapter_template:app --port 8082

Then point Cassandra at it:

    PATIENT_ENDPOINT=http://localhost:8082/chat
    PATIENT_PROJECT=<your Phoenix project>
    PATIENT_PROMPT_NAME=<name for patched prompt versions in Phoenix>
    BASELINE_PROMPT_FILE=<file holding your current system prompt>  # or let
    #   Cassandra extract it from your traces' llm.input_messages
    REPLAY_SHARED_SECRET=<random string, same value on both services>

The contract (also documented in cassandra/patient_client.py):

    POST /chat
      body:    {"message": str, "session_id": str, "system_override": str?}
      headers: X-Cassandra-Token: <REPLAY_SHARED_SECRET>
      reply:   {"reply": str, "total_tokens": int, "latency_ms": int}

Two non-negotiable rules this template already implements:

1. SECURITY — `system_override` swaps your agent's system prompt for one request.
   Honor it ONLY when session_id == "test" AND the shared secret matches;
   otherwise it is a prompt-injection surface on a public endpoint.
2. FEEDBACK-LOOP SAFETY — tag spans with `patient.session_id` and
   `patient.prompt_variant` so Cassandra's Watcher can filter out its own probe
   traffic instead of supervising itself forever.
"""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, Header
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from pydantic import BaseModel

app = FastAPI(title="Cassandra adapter for my agent")

# Use your existing OpenInference/OTLP tracer setup — the one already exporting
# to your Phoenix project. See patient/instrumentation.py for a minimal example.
_tracer = trace.get_tracer("my-agent")


# ---------------------------------------------------------------------------
# 1. IMPLEMENT THIS: call your actual agent.
# ---------------------------------------------------------------------------
async def run_my_agent(message: str, system_prompt: str | None) -> tuple[str, int]:
    """Run one turn of YOUR agent.

    `system_prompt` is None for normal traffic (use your default prompt) and a
    candidate prompt during Cassandra's sandboxed eval/replay/red-team runs.
    Return (reply_text, total_tokens). Tokens may be 0 if you don't track them —
    Cassandra then simply skips the cost/latency comparison.
    """
    raise NotImplementedError("wire this to your agent / LLM call")


# ---------------------------------------------------------------------------
# 2. The contract below usually needs no changes.
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str = "prod"
    system_override: str | None = None


def _resolve_override(req: ChatRequest, token: str | None) -> str | None:
    """Honor system_override only on Cassandra's sandboxed test path."""
    if req.session_id != "test":
        return None
    secret = os.environ.get("REPLAY_SHARED_SECRET")
    if secret and token != secret:
        return None
    return req.system_override


@app.post("/chat")
async def chat(req: ChatRequest, x_cassandra_token: str | None = Header(default=None)) -> dict:
    t0 = time.perf_counter()
    override = _resolve_override(req, x_cassandra_token)

    with _tracer.start_as_current_span("agent.chat", kind=SpanKind.SERVER) as span:
        # These attributes are what Cassandra's Watcher reads (and filters on).
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("input.value", req.message)
        span.set_attribute("patient.session_id", req.session_id)
        span.set_attribute("patient.prompt_variant", "candidate" if override else "current")

        reply, total_tokens = await run_my_agent(req.message, override)

        span.set_attribute("output.value", reply)
        span.set_attribute("llm.token_count.total", total_tokens)

    return {
        "reply": reply,
        "total_tokens": total_tokens,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "service": "my-agent-adapter"}
