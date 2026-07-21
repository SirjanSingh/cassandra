# Review: `multi-agent-v1` — multi-judge jury + open-the-fix-as-a-PR

**Reviewed commit:** `25c002a` — *feat: multi-judge jury + open-the-fix-as-a-PR*
**Author:** Kshitij Verma · **Date:** 2026-07-21 · **Reviewed:** 2026-07-21
**Base:** `cassandra-v2` @ `62790b4` (which already contains `origin/main`)

---

## 0. TL;DR

Two well-engineered, genuinely valuable features. Both are **opt-in and default-off**, so
merging them changes nothing about how Cassandra behaves today. The code quality is high —
pure functions separated from side effects, real tests, honest docstrings.

But two things need attention before either is turned on for a demo or a customer:

| # | Issue | Severity |
|---|-------|----------|
| **A** | With `JURY_SIZE=3`, **any non-unanimous panel mathematically cannot clear the existing `diagnosis_confidence_threshold=0.7` gate** → those incidents are silently never annotated in Phoenix. | **High** — behavioral regression the moment the flag is enabled |
| **B** | Jurors are the **same model at different temperatures**. Published research puts the effective independent-vote count of such a panel at **~2 even for 9 judges across 7 model families**; temperature-only variation lands at n_eff ≈ 1.94–2.18. You pay 3× cost for well under 3× information. | **High** — the feature's headline claim is weaker than it reads |
| C | A juror that raises is silently dropped; a 3-juror panel where 2 error reports `size=1, agreement=1.0` — i.e. **falsely unanimous and maximally confident**. | Medium |
| D | `open_pr` can commit onto the **currently checked-out branch** if both `git switch` calls fail (return codes unchecked on the fallback). | Medium |
| E | `JURY_SIZE=3` triples the evaluator's LLM burst — the exact burst already semaphore-bounded because Vertex `flash-lite` was 429-ing. | Medium (deployment) |

**Recommendation:** merge as-is (it is a fast-forward and default-off), then fix A and C
before ever setting `JURY_SIZE>1`, and reframe B as *self-consistency* rather than
*multi-agent diversity* — or make the jury genuinely multi-model, which the existing
`llm.py` backend selector already makes cheap.

---

## 1. Merge impact on the current codebase

### 1.1 Branch topology — good news

```
origin/main (8692b73)  ──┐
                          └── cassandra-v2 (62790b4) ── multi-agent-v1 (25c002a)
```

`origin/main` **is an ancestor** of `multi-agent-v1`, and so is `cassandra-v2`. There is
**no divergence and no merge conflict** — merging into `cassandra-v2` is a clean
fast-forward. (Kshitij fast-forwarded the branch up to `cassandra-v2` before starting, so
it already carries the grounding oracle and the CLI work that these features build on.)

### 1.2 Verified independently

I checked the branch out into a worktree and ran the suite myself:

```
91 passed, 1 warning in 28.55s
```

The commit message's claim is accurate. (+18 tests over the previous 66... the arithmetic
in the commit message says 66→91 which is +25, not +18 — a minor bookkeeping discrepancy,
not a problem. `test_jury.py` and `test_pr.py` account for the new files.)

### 1.3 Files touched — 15 files, +958/−17

| File | Change | Risk of regression |
|---|---|---|
| `cassandra/jury.py` | **new** — pure aggregation + async fan-out | none (unreferenced at default) |
| `cassandra/pr.py` | **new** — PR builder + git/gh driver | none (never called by the pipeline) |
| `cassandra/models.py` | `+JuryReport`, `Incident.jury` field | none — `Verdict` (the LLM response schema) deliberately left alone |
| `cassandra/config.py` | `+jury_size=1`, `+jury_max_temperature=0.8` | none at default |
| `cassandra/diagnostician.py` | `judge()` gains `temperature=0.0` kwarg; new `judge_panel()` | none at default — `size<=1` returns the exact old path |
| `cassandra/oracle.py` | `_judge_once` extracted, `_judge_fallback` added | none at default; **grounding stays PRIMARY** |
| `cassandra/loop_agent.py` | also dumps `reports/<id>.json` | low — extra file per cycle; unbounded growth over time |
| `cassandra/report.py` | postmortem prints a Jury line | none (guarded on `inc.jury`) |
| `cassandra/cli.py` | new `pr` subcommand | none — additive; `_SUBCOMMANDS` set extracted cleanly |
| `cassandra/mcp_server.py` | `+diagnose_jury`, `+prepare_fix_pr` | none — additive tools |
| `.env.example`, `docs/`, `tests/` | docs + config + tests | none |

**Architectural conventions respected.** `jury.py` imports only `models` (avoids the
`oracle` cycle); everything goes through `get_settings()`; all LLM calls go through
`llm.py`; nothing in `cassandra/` imports from `patient/`. The "never break the existing
CLI/MCP surface" instruction was honoured — only additions.

### 1.4 What actually changes when you flip the flags

- `JURY_SIZE=3` → **3× LLM calls** on (a) every production diagnosis and (b) every eval
  case that the deterministic grounding oracle abstains on. Plus the correctness issues in
  §3.
- `cassandra pr <id>` → **runs git commands in your working directory.** See §4.
- Every supervision cycle now writes `reports/<id>.json` regardless of flags.

---

## 2. What the features are actually for

### The Jury
Cassandra's weakest link has always been "one LLM call decides whether the agent failed."
The jury runs K inferences spread over temperature (juror 0 pinned at 0.0 as the
reproducible anchor), majority-votes, and turns **agreement** into a confidence multiplier
and **dissent** into a recorded artifact instead of a discarded sample. It upgrades the
*fallback* judge only — the deterministic grounding verifier from B1/B2 remains primary.

### The PR
The pipeline already produces a proven candidate prompt, a unified diff, replay evidence,
and a postmortem. `cassandra pr <id>` turns that into an actual GitHub pull request. This
is the difference between a dashboard and a teammate — it is the single most
demo-legible thing in the branch.

---

## 3. The jury: pros, cons, and what the research actually says

### 3.1 Pros

- **It is the standard answer to the standard objection.** "How do you know your judge is
  right?" is the first question any evaluation-tooling buyer asks. Having *any* calibrated
  answer beats having none.
- **Agreement is a real, cheap calibration signal.** Reporting "3 judges, 67% agreement,
  dissent recorded" is qualitatively more trustworthy than a bare `confidence: 0.85` that
  the model made up.
- **Dissent is a differentiator.** Most eval tools discard the minority sample. Surfacing
  it in the postmortem and the SSE payload is a nice product detail.
- **Fails safe by construction.** `aggregate_bools` requires a *strict* majority to PASS —
  an even split fails closed, which is the correct posture for a regression gate.
- **Genuinely zero-cost when off.** `size <= 1` short-circuits to the original call.

### 3.2 Con A (High) — the confidence gate breaks silently

`aggregate_verdicts` sets `confidence = agreement × mean_juror_confidence`. The existing
`Diagnostician` gate is `confidence >= 0.7`, and `compute_severity` buckets at 0.85/0.7/0.5.
Those thresholds were calibrated against *un-scaled* confidence.

Empirically (run against the branch):

| Panel | agreement | final confidence | severity | annotated in Phoenix? |
|---|---|---|---|---|
| 3 jurors, 3–0 | 1.00 | 0.950 | critical | ✅ |
| **3 jurors, 2–1** | 0.667 | **0.617** | medium | ❌ |
| 5 jurors, 4–1 | 0.80 | 0.760 | high | ✅ |
| **5 jurors, 3–2** | 0.60 | **0.570** | medium | ❌ |
| **2 jurors, 1–1** | 0.50 | **0.475** | low | ❌ |

With `JURY_SIZE=3`, a 2–1 panel caps at `0.667 × 1.0 = 0.667 < 0.7`. **No split 3-juror
panel can ever be annotated, no matter how confident the jurors are.** Turning on the
jury therefore silently *reduces* the number of incidents Cassandra records in Phoenix,
and squashes their severity — the opposite of "more reliable supervision."

*Fixes, cheapest first:*
1. Keep raw `mean_conf` as `Verdict.confidence` and store `agreement` separately on
   `JuryReport`; gate on `confidence >= threshold AND agreement >= agreement_threshold`.
   This keeps the two signals orthogonal instead of collapsing them into one number.
2. Or soften the scaling — e.g. `conf × (0.5 + 0.5·agreement)`, so a 2–1 split costs 17%
   rather than 33%.
3. Or make the threshold jury-aware (`threshold × expected_agreement`).

Option 1 is the right one: agreement and semantic confidence measure different things and
multiplying them destroys both.

### 3.3 Con B (High) — same-model temperature spread is the weakest form of diversity

This is the part where the marketing and the science diverge, and it is worth knowing
before the claim goes in a pitch.

The credible positive result for judge panels is **PoLL — "Replacing Judges with Juries"**
(Verga et al.): a panel of *three smaller models from disjoint model families*
**outperforms a single GPT-4 judge at 7–8× lower cost**, with measurably less
intra-model bias. Note the load-bearing phrase: **disjoint model families**. The gain
comes from decorrelating the *bias*, not from sampling more.

Against that, **"Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM
Evaluation Panels"** measured what actually happens:

- A **9-judge panel across 7 model families carries ≈ 2.18 effective independent votes**
  (mean pairwise error correlation φ̄ = 0.391; independence ratio 24.2%).
- Panel accuracy fell **22 points below** what independent voting predicts (72.0% vs 94.0%
  on MNLI) — the "Condorcet gap."
- Cross-family diversity barely helps: same-family φ = 0.437 vs cross-family φ̄ = 0.389.
  The *most* correlated pairs were cross-family (Claude × Gemini, φ = 0.603).
- Critically for us: **varying temperature (T=0 → 0.5) moved n_eff only within 1.94–2.18**,
  and chain-of-thought *increased* correlation.

The general self-consistency literature says the same: the same model with the same prompt
makes the same systematic mistakes regardless of seed; at error correlation ρ = 0.3, eight
samples collapse to ~2.6 effective votes, and most of the gain is captured by N = 5–10.

**What this means for Cassandra concretely:** `JURY_SIZE=3` on one Gemini flash-lite model
is *self-consistency sampling*, not a diverse jury. It will catch **sampling noise** —
borderline cases where the model genuinely wavers — which is real and useful. It will
**not** catch **systematic bias** — if flash-lite has a blind spot for a failure mode, all
three jurors share it and vote confidently wrong, and the falsely-unanimous 3–0 result now
gets *boosted* confidence. That is arguably worse than a single judge, because the panel
manufactures unearned certainty.

*The fix is small and high-leverage:* `llm.py` already selects among Vertex Gemini,
OpenAI, and OpenRouter at runtime. Make `JURY_SIZE` optionally a **`JURY_MODELS` list**
(e.g. `gemini-2.5-flash-lite, gpt-4o-mini, llama-3.3-70b via OpenRouter`) and the panel
becomes a real PoLL — defensible, citable, cheaper per unit of information, and a
genuinely differentiated product claim. Temperature spread can stay as the fallback when
only one backend is configured.

> Caveat worth keeping honest: hackathon compliance requires Gemini. A multi-model jury
> would need Gemini to remain the anchor juror (it already is — juror 0 at T=0).

### 3.4 Con C (Medium) — silent juror failure fakes unanimity

`deliberate()` uses `asyncio.gather(..., return_exceptions=True)` and filters exceptions
out. That is the right *resilience* call — a 429 on one juror shouldn't kill the panel —
but the aggregation then reports only the survivors:

```
3 jurors requested, 2 raised (e.g. Vertex 429s)
→ JuryReport(size=1, agreement=1.0)  →  confidence unscaled, "unanimous"
```

The panel that *failed hardest* reports as the *most trustworthy*. Given that flash-lite
429s are a documented, recurring condition on this project, this is not hypothetical.

*Fix:* carry `requested_size` alongside `size` on `JuryReport`, and either (a) refuse to
scale confidence upward when `size < requested_size`, or (b) treat a panel that lost >⅓ of
its jurors as degraded and fall back to the single-judge path explicitly.

### 3.5 Con E (Medium) — cost and quota

- **Cost:** linear in `JURY_SIZE`. 3× on every diagnosis *and* every abstaining eval case.
  On a 12-case synthesized dataset scored twice (baseline + candidate), that is up to 72
  extra calls per cycle instead of 24.
- **Quota:** `CLAUDE.md` records that `gemini-2.5-flash` was DSQ-exhausted on the trial
  project and the evaluator is already semaphore-bounded for exactly this reason.
  `JURY_SIZE=3` triples that burst. Expect 429s on the hosted demo unless the semaphore is
  re-tuned. The mitigating irony: those 429s hit the failure path in §3.4.
- **Latency:** jurors run concurrently, so wall-clock is roughly flat — good design.

### 3.6 Minor notes

- `_tally` documents "ties break toward the first-listed juror (juror 0 = the temp-0
  anchor)" — correct, but if juror 0 is the one that errored, `labels[0]` is now juror 1
  and the tie-break silently becomes non-reproducible. Related to §3.4.
- The jury only fires on the **fallback** path. On the ShopBot demo, the deterministic
  grounding oracle decides most cases, so `JURY_SIZE=3` may produce *no visible jury
  output at all* in a demo. Worth knowing before building a demo around it.

---

## 4. The PR feature: pros and cons

### 4.1 Pros

- **The strongest product-narrative move in the branch.** "Cassandra opens a PR with the
  fix and the evidence" is a story; "Cassandra writes a report" is a feature. It converts
  the whole pipeline into a visible deliverable.
- **The safety posture is genuinely right, and rare.** Never wired into the autonomous
  pipeline; three separate gates (`--dry-run` → local commit → `--push`); the MCP tool
  `prepare_fix_pr` returns a *draft only* so an agent can never push on its own. This is
  exactly the human-in-the-loop stance enterprise buyers ask about, and it is the kind of
  restraint that reads as maturity in a review.
- **Clean purity boundary.** `build_pr_content` and `load_incident` are pure and fully
  unit-tested; only `open_pr` shells out. That is why the offline test suite can cover it.
- **The PR body is good.** Pass-rate delta as the headline (`43% → 91% (+48%)`) plus
  replay FIXED/STILL BROKEN plus the full postmortem is a genuinely reviewable PR.

### 4.2 Con D (Medium) — it can commit to your current branch

```python
if _run(["git", "switch", "-c", branch]).returncode != 0:
    _run(["git", "switch", branch])      # ← return code not checked
Path(target).write_text(inc.candidate_prompt, ...)
_run(["git", "add", target]); commit = _run(["git", "commit", ...])
```

If both switches fail (detached HEAD, dirty tree blocking the switch, a ref-name collision),
execution continues and **the prompt file is overwritten and committed onto whatever branch
is currently checked out** — potentially `main`. The commit succeeds, so no error surfaces.

*Fix:* check the second `git switch`, and assert `git rev-parse --abbrev-ref HEAD == branch`
before writing. Also worth refusing to run on a dirty working tree, or at minimum warning —
`git switch -c` carries uncommitted changes onto the new branch.

### 4.3 Other PR-feature notes

- **CWD-coupled.** `open_pr` runs git in the process's working directory, implicitly
  assuming the supervised agent's repo *is* the repo you launched Cassandra from. For the
  real use case (Cassandra supervising someone else's agent) that is usually false. A
  `--repo PATH` argument, with all git calls taking `-C <path>`, would fix it.
- **Partial-failure state.** If `git push` or `gh pr create` fails, `open_pr` raises after
  the local branch + commit already exist. `PRResult` supports reporting that
  (`committed=True`) but the exception path discards it. Returning a failed `PRResult`
  instead of raising would leave the caller in a recoverable state.
- **Leftover artifact.** `reports/<id>.prbody.md` is written and never cleaned up.
- **`reports/` growth.** `loop_agent` now writes a full serialized `Incident` JSON per
  cycle with no retention policy. On a long-running supervisor this grows unbounded.
- **Known limitation, already documented:** ShopBot's prompt is a Python constant, not a
  file, so the demo can't exercise the file-commit path without `--prompt-file` or
  `BASELINE_PROMPT_FILE`. Kshitij flagged this in the session note. Adding a demo prompt
  *file* to ShopBot is a small change that would make `cassandra pr --push` demoable
  end-to-end.
- **`--push` is untested offline by design** and has never been run. Exercise it against a
  scratch repo before any demo.

---

## 5. How this benefits the product

**Strategic read.** These two features move Cassandra along the two axes that decide
whether an eval/observability tool gets bought:

1. **Trustworthiness of the verdict** (jury) — the objection every competitor in this space
   fields. Braintrust and Opik both ship judge tooling; a *calibrated* judge with recorded
   dissent is a real talking point, and becomes a genuinely defensible one if it goes
   multi-model per §3.3.
2. **Closing the loop** (PR) — the thing that separates "observability" from "remediation."
   Most competitors stop at "here is a scorecard." Cassandra now goes diagnose → prove →
   **open the fix**. That is the whole pitch in one sentence, and the human-in-the-loop
   gating is what makes it sellable rather than alarming.

**Where they land in the existing architecture.** Both slot into the layered eval design
from `EVAL_PLAN.md` without disturbing it: deterministic grounding stays L0/L1 primary; the
jury upgrades the L2 LLM fallback; the PR is a new terminal stage after replay/red-team.
Nothing about the 8-stage pipeline contract changed.

**Honest limitation for positioning.** As shipped, the jury is *self-consistency*, not a
*panel of diverse judges*. It is fine to ship — but describing it externally as
"multi-agent inference" invites exactly the critique in §3.3 from anyone who has read the
PoLL follow-up literature. Either say "self-consistency with agreement-calibrated
confidence" (accurate, still good) or spend the small effort to make it multi-model
(better claim, better product, ~a day of work given `llm.py`).

---

## 6. Recommended actions

**Merge now** — fast-forward, default-off, 91 tests green, no conventions violated.

Before `JURY_SIZE>1` is enabled anywhere:

1. **[High]** Decouple agreement from confidence (§3.2) — don't multiply; gate on both.
2. **[High]** Track `requested_size` vs surviving jurors; never report a degraded panel as
   unanimous (§3.4).
3. **[Med]** Re-tune the evaluator semaphore for the 3× burst, or cap `JURY_SIZE` when the
   Vertex backend is active (§3.5).
4. **[Med]** Decide the positioning: self-consistency (accurate today) vs. a real
   multi-model `JURY_MODELS` panel (§3.3). The latter is the better product.

Before `cassandra pr --push` is used:

5. **[Med]** Check the fallback `git switch` return code; assert the branch actually
   switched before writing (§4.2).
6. **[Med]** Add `--repo PATH` and run git with `-C` (§4.3).
7. **[Low]** Return a failed `PRResult` instead of raising after a successful local commit;
   clean up `.prbody.md`; add a retention policy for `reports/`.
8. **[Low]** Give ShopBot a prompt *file* so the PR path is demoable end-to-end.

---

## Sources

- [Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models (PoLL)](https://arxiv.org/abs/2404.18796)
- [Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation Panels](https://arxiv.org/html/2605.29800)
- [RoPoLL: Robust Panel of LLM Judges](https://arxiv.org/html/2606.30931v1)
- [How Reliable is Multilingual LLM-as-a-Judge? (EMNLP 2025 Findings)](https://aclanthology.org/2025.findings-emnlp.587.pdf)
- [Verdict: A Library for Scaling Judge-Time Compute](https://arxiv.org/pdf/2502.18018)
- [Self-consistency: majority-vote across reasoning samples](https://zeroentropy.dev/concepts/self-consistency/)
- [Exploring LLM-as-a-Judge (Weights & Biases)](https://wandb.ai/site/articles/exploring-llm-as-a-judge/)
