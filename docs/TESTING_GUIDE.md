# Cassandra — Tester's Guide (v0.2.0 alpha)

> You've been handed an early build of **Cassandra** to try out. This guide gets you from
> zero to a running demo and tells you what's worth poking at + how to report back.
> Est. time: **5 min** for the smoke test, **~20 min** for the full local demo.

## 1. What Cassandra is (the 30-second version)

Cassandra is a **meta-agent that supervises other LLM agents**. It watches a production
agent's traces (via Arize Phoenix), catches when the agent hallucinated / used a tool wrong /
drifted, turns each failure into an adversarial eval set, proposes a hardened prompt, replays
the original failing input against the fix, and red-teams it — writing everything back to
Phoenix. The bundled demo victim is **"ShopBot"** (`patient/`), a deliberately fragile support
bot that invents refund policies.

Full architecture: see `docs/CODEBASE_MAP.md` and `docs/SYSTEM_DESIGN.md` in the repo.

## 2. Install

You were given `cassandra_ai-0.2.0-py3-none-any.whl` (attached to the GitHub release).

```bash
python -m venv .venv           # Python 3.11 or 3.12
# Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
pip install cassandra_ai-0.2.0-py3-none-any.whl
```

> The import package is `cassandra`; the distribution is `cassandra-ai`. Installing the wheel
> pulls its dependencies from real PyPI normally.

## 3. Smoke test (no keys, no infra — 1 minute)

```bash
cassandra            # should print the "Cassandra" ASCII banner + a command list, v0.2.0
cassandra --help
cassandra dashboard --help
```

✅ If the banner renders and `--help` works, the package installed correctly. That alone is a
useful data point — please report your **OS + Python version** and whether this worked.

## 4. Full local demo (needs an LLM key + Phoenix)

Cassandra needs three things to do real work:

1. **An LLM key.** Backend is chosen by env (precedence in `cassandra/llm.py`):
   `OPENAI_API_KEY` → OpenAI; else a `GEMINI_API_KEY` starting `sk-or-` → OpenRouter; else
   Vertex Gemini. Easiest: a free Gemini key from https://aistudio.google.com.
2. **A Phoenix instance** — run one locally in Docker:
   `docker run -p 6006:6006 arizephoenix/phoenix`
3. **Node / npx** — Cassandra shells out to `npx @arizeai/phoenix-mcp` to talk to Phoenix.

Create a `.env` in your working directory (see the repo's `.env.example` for every key):

```bash
GEMINI_API_KEY=your-key-here
GOOGLE_GENAI_USE_VERTEXAI=false
PHOENIX_BASE_URL=http://localhost:6006
PATIENT_ENDPOINT=http://localhost:8082/chat
```

Then, in three terminals (all from the venv):

```bash
# 1. the victim agent (ShopBot) — ships inside the wheel
python -m uvicorn patient.agent:app --port 8082

# 2. the dashboard / cockpit  (open http://localhost:8085/cockpit)
cassandra dashboard --port 8085

# 3. drive ONE full supervision cycle
cassandra run
```

In the cockpit you can type a customer message (e.g. *"What's the refund policy for Germany?"*),
watch ShopBot fabricate an answer, then watch Cassandra catch it and run the full
diagnose → synthesize → patch → replay → red-team pipeline. The **"Grade my own diagnoses"**
button runs Cassandra's self-evaluation.

## 5. What to look at / report back

Please note anything in these buckets:

- **Install:** did `pip install <wheel>` succeed on your OS/Python? Any dependency errors?
- **CLI:** does `cassandra` / each subcommand behave? Any confusing output or crashes?
- **Demo (if you set up keys):** did `cassandra run` complete a cycle? Did the cockpit render?
- **Docs:** was this guide enough to get going? Where did you get stuck?
- **Rough edges:** anything that felt broken, unclear, or surprising.

Report back to Sirjan with: **OS, Python version, what you ran, and what happened** (paste any
error text). Small notes are fine — this is an alpha, we expect sharp edges.

## 6. Known limitations (by design, for this alpha)

- Not turnkey: you must bring your own LLM key + Phoenix + Node. This is intentional for v0.1.
- The React web UI is Docker-only; the pip build serves the self-contained cockpit at `/cockpit`.
- The bundled ShopBot is a demo; supervising your *own* agent is possible but needs the
  "Bring your own agent" setup in `docs/WORKFLOWS.md`.
- **Don't expose the dashboard publicly** — `/ask` and `/selfeval` are unauthenticated and
  trigger LLM calls (they'd let anyone burn your API quota). Keep it on localhost.
