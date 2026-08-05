# Security audit + load characterisation — `cassandra-v2`

**Audited:** 2026-08-05 · **Branch:** `cassandra-v2` @ `5ae9f85` · **Suite at audit time:** 73 passed

Scope: static audit of the framework and both deployment paths (GCE VM + ngrok, and the
Cloud Run / `cloudbuild.yaml` path), plus an **offline** stress harness
(`scripts/stress_probe.py` — no network, no LLM spend) against the stateful cores.

**Not done:** live penetration testing against the deployed ngrok/GCP endpoints. That is
production infrastructure and probing it costs real LLM budget — it needs explicit
authorisation and a maintenance window. Every finding below is derived from source and from
offline reproduction.

Companion docs: [`sessions/2026-08-05-code-audit-and-launch-plan.md`](sessions/2026-08-05-code-audit-and-launch-plan.md)
(correctness audit + launch plan), [`DEPLOYMENT.md`](DEPLOYMENT.md), [`../PRODUCT_PLAN.md`](../PRODUCT_PLAN.md).

---

## 0. Summary

| Sev | # | Finding |
|---|---|---|
| **CRITICAL** | 1 | `system_override` fails open when `REPLAY_SHARED_SECRET` is unset — full prompt takeover, invisible to the Watcher |
| **CRITICAL** | 2 | Unauthenticated LLM-spend endpoints on the public internet (`/chat`, `/ask`, `/selfeval`) |
| **CRITICAL** | 3 | No `--max-instances` + a supervision loop started on **every** dashboard instance |
| **HIGH** | 4 | Cloud Run CPU throttling means the autonomous loop does not reliably run at all |
| **HIGH** | 5 | Phoenix API key passed as a command-line argument (world-readable via `ps`) |
| **HIGH** | 6 | `@arizeai/phoenix-mcp@latest` — unpinned third-party code executed at runtime in prod |
| **HIGH** | 7 | `load_dotenv(override=True)` — a `.env` silently overrides injected secrets |
| **MED** | 8 | Dashboard container runs as root (`-u 0`), negating the Dockerfile hardening |
| **MED** | 9 | Tool dispatch trusts model output (`KeyError`/`TypeError` → unhandled 500) |
| **MED** | 10 | `vm_startup.sh` pins a **stale image** — any VM reboot rolls production back |
| **MED** | 11 | ngrok is the entire ingress; single VM, no WAF/DDoS, no rollback |
| **MED** | 12 | No audit logging, no budget alerts; `reports/` and cursor state unmanaged |
| **LOW** | 13 | Misleading config defaults (`phoenix_api_key="replace-me"`, `gemini-3-pro`, `state_backend=firestore`) |

**Clean:** no secrets in git history (pattern-scanned across all tracked files), `.env` never
tracked, `.gitignore` correct, timing-safe secret compare present, request length caps present,
non-root user in the Dockerfile, sdist allowlist prevents over-inclusion.

---

## 1. CRITICAL findings

### 1.1 `system_override` fails open, and the hijack is invisible to supervision

`patient/agent.py:67`

```python
if secret and not hmac.compare_digest(token or "", secret):
    return None
```

When `REPLAY_SHARED_SECRET` is unset the entire check is skipped, leaving only
`session_id == "test"` (`patient/agent.py:63`) — which is attacker-controlled on an
unauthenticated endpoint. One request replaces the agent's whole system prompt:

```json
{"message": "...", "session_id": "test", "system_override": "<attacker prompt>"}
```

**The compounding factor:** `watcher.py:48` filters out `session_id == "test"` spans (correctly —
it prevents self-supervision loops). So hijacked traffic is *also invisible to Cassandra*. Full
agent takeover plus a supervision blind spot, in a single request.

Both deploy paths currently set the secret, so this is not live exposure today — but there is **no
startup assertion**, so a single missing env var is total compromise. Previously logged as
"deferred by design" in `sessions/2026-07-21-cli-banner-pypi-launch.md` step 7b; **that
classification is wrong and is superseded by this document.**

**Fix:** fail closed. Refuse `system_override` when no secret is configured, and refuse to boot in
non-dev mode without one.

### 1.2 Unauthenticated LLM-spend endpoints

`deploy/cloudbuild.yaml` passes `--allow-unauthenticated` to **both** Cloud Run services; the
ngrok URL is public by construction. There is no auth, rate limiting, quota, or captcha anywhere
in the codebase.

| Endpoint | Cost per request | Input needed |
|---|---|---|
| `patient/agent.py:112` `/chat` | 4000 chars × 4-iteration tool loop | a message |
| `dashboard/main.py:74` `/ask` | proxies to the Patient, 300s timeout | a message |
| `dashboard/main.py:84` `/selfeval` | **the entire trap library through the LLM** | **no body at all** |

`/selfeval` is the cheapest denial-of-wallet vector: an empty POST in a loop. Length caps
(`max_length=4000` / `2000`) bound a single request but not the request *rate*.

**Fix:** admin token on `/selfeval` (or drop it from public routing), per-IP rate limits on the
rest, and service-to-service auth on dashboard→Patient so the Patient need not be public at all.

### 1.3 No instance cap, and a supervision loop per instance

`dashboard/main.py:34-57` starts `watcher_loop()` in `@app.on_event("startup")` — so **every**
container runs a complete supervision pipeline. `deploy/cloudbuild.yaml` sets no
`--max-instances`, so the Cloud Run default of 100 applies.

Worst case: 100 concurrent pipelines polling the same Phoenix project and running the same 8-stage
LLM cycle over the same incidents — with the state layer providing no mutual exclusion (§3.2).
Cost blowup and duplicate Phoenix writes.

**Fix (stopgap):** `--max-instances=1` now. **Fix (real):** §4, P1 — split the worker out.

---

## 2. HIGH findings

**2.1 Cloud Run CPU throttling breaks the autonomous loop.** Cloud Run freezes CPU outside
request handling unless CPU-always-allocated or `--min-instances` is set. Neither is configured,
so the background loop is throttled/suspended between HTTP requests and only progresses
incidentally while traffic exists. The "autonomous meta-agent" property does not hold on the
Cloud Run path. (The GCE VM path is unaffected — it is a plain long-running container.)

**2.2 API key in argv.** `phoenix_mcp.py:58-61` appends `--apiKey <key>` to
`StdioServerParameters.args`. Command lines are world-readable via `ps` / `/proc/*/cmdline` and
appear in crash dumps (CWE-214: Invocation of Process Using Visible Sensitive Information). The
env is already populated at `:65-68`; the code comment records that the MCP server ignores it, so
this needs a config-file or upstream fix rather than simply deleting the flag.

**2.3 Unpinned runtime dependency on third-party code.** `config.py:31` defaults
`phoenix_mcp_args` to `-y,@arizeai/phoenix-mcp@latest`, and `phoenix_mcp.py:70` spawns it per
session. `@latest` resolves **from the npm registry, at runtime, in production**: a compromised or
merely breaking release changes production behaviour with no deploy and no review, and npm
availability becomes a hard runtime dependency of the supervision loop.

**2.4 `load_dotenv(override=True)`.** `config.py:10` — a `.env` present in the image or CWD
overrides real environment variables, including injected Secret Manager values. Backwards for
production; a silent-misconfiguration trap.

---

## 3. Load characterisation (measured)

Reproduce with `python scripts/stress_probe.py` — offline, no external services.

### 3.1 Grounding oracle — no ReDoS, but the verdicts are wrong

Cost is linear in answer length; no catastrophic backtracking:

| Answer size | Time |
|---|---|
| 1 KB | 1.33 ms |
| 10 KB | 2.69 ms |
| 104 KB | 25.6 ms |
| 525 KB | 99.3 ms |

Precision, against a ledger of `get_refund_policy → {found:false}`:

| Input | Verdict | Correct |
|---|---|---|
| "Your order shipped 3 days ago" | HALLUCINATION | ✗ false positive |
| "I can't provide the refund policy — orders usually ship within 2 days" | HALLUCINATION | ✗ flags an honest decline |
| "I couldn't find that information." | OK | ✓ |
| "Refunds are available within 30 days" | HALLUCINATION | ✓ |
| Tool returns **DHL / 2026-08-09**; answer says **"UPS, arriving 2026-12-25"** | **OK** | ✗ **false negative** |

Three of five wrong. This empirically confirms the correctness findings in the
[2026-08-05 session note](sessions/2026-08-05-code-audit-and-launch-plan.md) §2 — including the
value-mismatch hole, which passes a flat contradiction of a *successful* tool call.

### 3.2 State layer — loses data under any concurrency

| Probe | Measured result |
|---|---|
| Dedupe window (`state.py:45`, `:70`) | 500-entry cap confirmed: after 600 marks, span #0 is forgotten and **re-processed** |
| Two instances, one backing file | A marks span-A, B marks span-B → file contains **only span-B** (lost update) |
| Firestore read-modify-write race (same code shape) | Concurrent marks → **only one survives** → duplicate supervision + duplicate LLM spend |
| `mark_seen` cost | Full file rewrite per call, ~0.55 ms |
| `seen()` cost | Linear list scan |

`FirestoreState.mark_seen` is a non-transactional read-modify-write of an array
(`state.py:69-71`), and `seen()` performs a **full document read per span** — 50 reads per poll
per instance. All of it is **synchronous blocking I/O called from async code**
(`watcher.poll` → `state.seen`), so it stalls the event loop, including SSE and `/ask`.

### 3.3 Event bus — unbounded, no backpressure

`events.py:20-22` awaits `q.put()` on unbounded queues. Measured with a stalled subscriber:
**1408 bytes/event**, queue depth reached 20,000 with zero drops or throttling.

> A single stalled SSE client (suspended tab, dead TCP) costs **~5 MB/hr at 1 event/sec**,
> unbounded, for the process lifetime.

It is also in-process only: with more than one instance, each client sees only the events from
whichever instance it connected to.

### 3.4 Pipeline — confirmed incident loss

Batch of 3 spans with one processed per cycle: **1 incident permanently dropped per burst**,
invisible to the next poll because `watcher.py:86` advanced the cursor past it while
`loop_agent.py:59` returned after the first failure.

---

## 4. Required production changes

### P0 — before any further public exposure (~15h)

1. **Fail closed** on `REPLAY_SHARED_SECRET`; assert at startup outside dev mode. (§1.1)
2. Admin token on `/selfeval` (or remove from public routing); per-IP rate limits on `/chat` and
   `/ask`; drop `--allow-unauthenticated` on the Patient in favour of service-to-service auth. (§1.2)
3. `--max-instances=1` on the dashboard as an immediate stopgap. (§1.3)
4. Pin `@arizeai/phoenix-mcp` to an exact version; stop passing the key via argv. (§2.2, §2.3)
5. `load_dotenv(override=False)` for non-dev. (§2.4)

### P1 — the architecture change that enables scale (~72h)

6. **Split the supervision worker out of the web service.** Web = stateless, N instances, no
   background loop. Worker = exactly one leader-elected process with CPU always allocated
   (Cloud Run Job, GKE, or the VM). Resolves §1.3 and §2.1 together. **Highest-value change in
   this document.**
7. **Real state store with atomic claims** — Postgres with a unique constraint on `span_id`, or
   Firestore transactions, plus a lease so only one worker claims an incident. Unbounded dedupe
   via a table, not a 500-element array. Make the calls async. (§3.2)
8. **Queue-based pipeline** — the Watcher enqueues *all* incidents; workers consume with bounded
   concurrency. Fixes the per-burst incident loss. (§3.4)
9. **Replace the in-process bus** with Redis/Pub-Sub; give SSE queues a bounded size with
   drop-oldest. (§3.3)

### P2 — ingress and operations (~28h)

10. **Retire ngrok** — Cloud Run behind a Google HTTPS LB + Cloud Armor, or Cloudflare Tunnel:
    TLS you control, WAF, DDoS protection, a real domain. (§1 MED 11)
11. **CI that gates deploys** — run `pytest` + `ruff` in `cloudbuild.yaml` *before* the deploy
    steps. Today a broken build deploys straight to production.
12. Health checks, structured logging, error tracking, and **hard budget alerts on Vertex/OpenAI
    spend**. Rotate `reports/`; mount a volume for cursor state on the VM.
13. **Rotate the keys that were in `.env`** — open since 2026-06-05.
14. Un-root the dashboard container (rootless port + reverse proxy, or `NET_BIND_SERVICE`);
    refresh the stale image pin in `vm_startup.sh` and add a health check. (§1 MED 8, 10)

**Total ≈115h on top of the ~270h launch plan — roughly one additional month at the current
two-person part-time pace. Revised realistic launch: 3.5–4 months.**

---

## 5. Cost per incident — the open commercial unknown

The per-incident LLM cost is **not currently measured**, and pricing cannot be set without it.
One `run_once()` cycle is approximately:

- 3 reasoning calls — Diagnostician, RootCauseAnalyst, Synthesizer
- 4 baseline probes + 4 candidate probes (`evaluator.py:30`, `_MAX_CASES = 4`)
- 1 Patcher call, 1 replay probe
- 12 red-team probes (`redteam.py:21`, 6 attacks × before/after)

…where **each probe drives the supervised agent through its own multi-call tool loop**
(`patient/agent.py:173`, up to 4 iterations). Order of magnitude: **~25 agent invocations + ~5
judge calls per incident.**

Instrument this before Tier 3 of the launch plan. At 200 incidents/month per customer the
arithmetic determines whether the product has a gross margin — and it is the strongest argument
for the distilled-judge work described in the session note §4.
