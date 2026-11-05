# Jury & PR — the two new features, in plain English

Two additions to Cassandra (`multi-agent-v1`), written so anyone can follow them.

- **Jury** → don't trust *one* AI judge. Ask several and take a vote.
- **PR** → don't just report the fix. Open it as a GitHub pull request for a human to approve.

---

## 1. The Jury 🧑‍⚖️🧑‍⚖️🧑‍⚖️

### The problem it solves
Cassandra decides "did the agent mess up?" partly with an **LLM-as-judge** — one AI call
giving one opinion. The obvious objection: *"How do you know that one judge is right?"* A
single opinion has no way to tell you how sure it is.

### What we built
When needed, Cassandra now asks the judge **several times instead of once** (a "panel of
jurors") and takes the **majority vote**. Two useful things fall out for free:

- **Agreement** — how many jurors agreed. All 3 agreed → very confident. 2‑vs‑1 → less
  confident. We literally lower the confidence score when the panel is divided.
- **Dissent** — the minority opinion is *recorded*, not thrown away.

To make sure the jurors actually think differently (and don't just repeat the same answer),
each juror runs at a slightly different "temperature" (creativity dial). Juror #1 is always
the steady, predictable one; the others are nudged to be more exploratory.

### Where it's used
- The **Diagnostician** (deciding hallucination / tool-failure / etc.).
- The **oracle's fallback judge** (used only when the fast, rule-based check can't decide).

> Important: the deterministic, rule-based grounding check is still the *primary* way
> Cassandra decides pass/fail. The jury only strengthens the *fallback* LLM judgment. See
> [`EVAL_PLAN.md`](../EVAL_PLAN.md).

### How to turn it on
It's **off by default** (`JURY_SIZE=1` = the original single judge, nothing changes). Turn it
on in `.env`:

```bash
JURY_SIZE=3              # ask 3 judges and vote (a good panel size)
JURY_MAX_TEMPERATURE=0.8 # how much the jurors are allowed to differ
```

⚠️ Each juror is one extra LLM call, so `JURY_SIZE=3` costs ~3× per judged item. Raise it
deliberately. **Restart the server after changing `.env`** (settings are cached).

### Try it without any setup (via the MCP tool)
```
diagnose_jury(
  customer_input = "What's the refund window for Germany?",
  agent_output   = "Germany has a 30-day return policy.",
  jurors         = 3
)
```
Returns the verdict **plus** `jury: { size, agreement, votes, dissent }`.

---

## 2. Open the fix as a Pull Request 🔀

### The problem it solves
Cassandra already proves a prompt fix works. Before, it wrote a report file and stopped. A
human still had to copy the fix into the codebase by hand.

### What we built
A completed supervision cycle can now be **opened as a GitHub pull request** — the same way a
teammate would submit a fix:

1. make a new branch
2. write the improved prompt into the agent's prompt file
3. commit it
4. push and open a PR — with the full postmortem (diagnosis, before/after, pass-rate
   improvement) as the PR description

Then a human reviews and clicks merge. **Cassandra never merges anything itself.**

### Safety (this is deliberately cautious)
Opening a PR changes real things, so it's gated:

- It is **never** done automatically by the pipeline — only when *you* run the command.
- `--dry-run` shows you exactly what it *would* open and changes **nothing**.
- Without `--push` it only prepares the change **locally** (branch + commit) and prints the
  command to open the PR.
- **`--push` is the only flag that actually talks to GitHub.**

### How to use it
After a supervision cycle finishes (it saves `reports/<incident-id>.json`):

```bash
# 1. Preview the PR — safe, touches nothing
cassandra pr inc-1234 --dry-run

# 2. Prepare it locally (branch + commit), don't push yet
cassandra pr inc-1234 --prompt-file prompts/system_prompt.txt

# 3. Actually open the PR on GitHub
cassandra pr inc-1234 --prompt-file prompts/system_prompt.txt --push --base main
```

| Flag | What it does |
|------|--------------|
| `--dry-run` | Show the PR title/branch/body; change nothing. |
| `--prompt-file PATH` | The agent's system-prompt file to update (or set `BASELINE_PROMPT_FILE`). |
| `--base BRANCH` | Base branch for the PR (default `main`). |
| `--branch NAME` | Override the auto-generated branch name. |
| `--push` | Push the branch and run `gh pr create` (the outward-facing step). |

> Needs `git` and the GitHub CLI (`gh`) installed and logged in for `--push`.
> The demo ShopBot keeps its prompt in Python code, not a file — so for a live PR demo you
> need a real prompt *file* (via `BASELINE_PROMPT_FILE` or `--prompt-file`).

### Draft it from an IDE (MCP)
`prepare_fix_pr(incident_id)` returns the ready-to-use PR title/branch/body as a **draft
only** — it never pushes. Handy inside Claude Desktop / Cursor.

---

## Quick reference

| | Jury | PR |
|---|---|---|
| **New file** | `cassandra/jury.py` | `cassandra/pr.py` |
| **Turn on** | `JURY_SIZE=3` in `.env` | run `cassandra pr <id>` |
| **Default** | off (single judge) | manual only |
| **MCP tool** | `diagnose_jury` | `prepare_fix_pr` (draft) |
| **Safety** | just costs more LLM calls | dry-run / local / `--push` gates |

For the deeper "why", see [`docs/sessions/2026-07-21-jury-and-pr-features.md`](sessions/2026-07-21-jury-and-pr-features.md).
