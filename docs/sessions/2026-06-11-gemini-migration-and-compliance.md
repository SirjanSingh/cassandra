# Session Log: 2026-06-11 (deadline day, part 2) - Gemini Migration, Agent Engine, Compliance

## Why this happened

A re-read of the official hackathon rules surfaced a **disqualification-level compliance gap**:
the rules require the agent to be *"powered by Gemini"* and state *"All other artificial
intelligence tools are not permitted"* / *"services that directly compete with Google Cloud …
not permitted."* The live demo was running on **OpenAI (`gpt-4o-mini`)** — a direct Gemini
competitor. That is a Stage-One pass/fail risk regardless of quality. This session migrated the
hosted deployment to **Vertex AI Gemini** and deployed to **Vertex AI Agent Engine**, fixing a
chain of real bugs that only surfaced once Gemini was actually exercised end-to-end.

## Vertex AI Agent Engine — DEPLOYED (live)

`deploy/agent_engine.py`. Iterated `agent_engines.create()`; each failure was a real, distinct cause:
1. **Wrong project** — stale `.env` `GOOGLE_CLOUD_PROJECT` won over the env override -> added
   `AGENT_ENGINE_PROJECT` env that takes precedence; forced `cassandra-498318`.
2. **"failed to start and cannot serve traffic"** — a bare ADK `LoopAgent` has no servable
   interface -> wrapped in `vertexai.preview.reasoning_engines.AdkApp`.
3. **`ModuleNotFoundError: No module named 'vertexai'`** in the runtime container -> a custom
   `requirements` list REPLACES the defaults, so added
   `google-cloud-aiplatform[agent_engines]` + `cloudpickle` (the AdkApp is unpickled at runtime
   and imports vertexai).
4. Dropped `patient` from `extra_packages` (only `cassandra` is imported by the agent graph).

**Result:** live resource
`projects/905502723393/locations/us-central1/reasoningEngines/1519338702365523968`, verified
queryable (exposes AdkApp session/query operations). Prereqs: ADC quota project set, GCS
staging bucket `gs://cassandra-498318-agent-engine`, VM/runtime SA `roles/aiplatform.user`.

## Switching the hosted VM demo to Vertex Gemini

`deploy/vm_startup.sh`: stop passing `OPENAI_API_KEY` to the containers (so `llm.py` falls
through to Vertex), set `GOOGLE_GENAI_USE_VERTEXAI=true`, `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION=us-central1` (a real region, never `global`), `GEMINI_MODEL`. Granted the
VM service account `roles/aiplatform.user` (ADC via the metadata server inside the container).

### Three bugs that only appeared on the Gemini path (all fixed)

1. **`llm.py` genai client GC'd mid-request** -> `RuntimeError: Cannot send a request, as the
   client has been closed`. The Gemini branch did
   `await _gen_with_retry(lambda: _client().aio.models.generate_content(...))` — the
   `_client()` temporary had no reference, so it was garbage-collected (closing its httpx
   session) before the coroutine finished. The patient's `/chat` was unaffected because it
   holds the client in a named var. **Fix:** wrap each call in an `async def _call()` that holds
   `client` in a local across the await (`cassandra/llm.py`, both `structured()` and `text()`).
   Without this the whole supervision loop silently no-ops on Gemini (the loop's bare
   `except` printed an empty error string, which masked it).
2. **`gemini-2.5-flash` DSQ exhausted** -> sustained `429 RESOURCE_EXHAUSTED` on the trial
   project, defeating even the 7-step backoff. Credits do NOT buy Dynamic Shared Quota headroom.
   **Fix:** switched to **`gemini-2.5-flash-lite`**, which draws from a less-contended DSQ pool
   (4/4 sequential calls clean). Stages diagnose..patch then all pass.
3. **`eval_candidate` -> `httpx.ReadTimeout`** — the evaluator fired all 8 probes at the live
   agent concurrently; each probe drives Gemini (with tool loops), so the burst bottlenecked on
   DSQ and blew the 60s HTTP timeout. **Fix:** `Semaphore(3)` around the probe calls + raise the
   client timeout to 120s (`evaluator.py`, `redteam.py`). diagnose..patch verified OK on
   flash-lite; this lets the full cycle finish.

## URL / hosting compliance (the "ngrok = disqualify?" question)

No. The rules require a working hosted web URL and use of Google Cloud *services* — they do NOT
mandate a `*.run.app` domain. The app runs on a **GCE VM (Google Compute Engine)** in
`cassandra-498318`; ngrok is only the ingress tunnel (Cloud Run + GCE external IP are both still
edge-gated for this fresh account — re-tested, still 404). One sentence in the Devpost writeup
explains the GCE-behind-tunnel setup. Hosted URL: **https://elianna-unpolymerized-confidingly.ngrok-free.dev**.

## Also fixed this session

- **Patched-stage Phoenix link** used the prompt *name* (`/prompts/<name>`, 404s); Phoenix routes
  prompts by base64 node id. Now links to `/prompts` (list page, always resolves). `patcher.py`.
- Confirmed the Phoenix deep-links are owner-only (Arize Cloud spaces are private; no anonymous
  public view) — use them in the logged-in demo + screenshots, not as judge-clickable links.

## Verification

39 offline tests pass, ruff clean. Live (gemini-2.5-flash-lite): `/ask` returns a fragile Gemini
reply; diagnose/rootcause/synthesize/eval_baseline/patch all OK in-container; spans flow to
Arize Cloud Phoenix; eval_candidate timeout fixed via the concurrency bound (pending final
full-cycle re-verify on the rebuilt image `b623fbe-react`).

## Commits (origin/main, this session)

`0ccb29a` patched-link · `857e970` Agent Engine deploys (live) · `c5cb638` AE docs ·
`ac6ad70` VM->Vertex Gemini · `d7f2e6d` llm client-lifecycle fix · `d93e5e8` flash-lite +
image bump · `b623fbe` evaluator concurrency/timeout.

## Open items

- Final full-cycle re-verify on `b623fbe-react` (rebuild + VM reset in progress).
- Demo video (≤3 min) + Devpost writeup (`docs/PITCH.md`).
- Post-submission: delete the VM (`gcloud compute instances delete cassandra-vm --zone
  asia-south1-b`), rotate the ngrok token + old keys.
