# Cassandra Evaluation Plan

> Status: **proposal for review — nothing implemented yet.**
> Author's note: this document deliberately shows the reasoning, not just the conclusion.
> If you only read one section, read **§3 (the core realization)** and **§5 (the findings)**.

---

## 1. TL;DR (the opinionated version)

Cassandra leans on LLM-as-judge in **six** places. For the task Cassandra actually
supervises — *tool-using agents that fabricate facts their tools didn't return* — most of
that judging is a **crutch standing in for a grounding check that the telemetry already
makes deterministic**. The agent's tool-call log is structured, closed-world ground truth:
`get_refund_policy("DE") → {found: false}` and `lookup_order("A1002") → {carrier: null}` are
*facts*, not opinions. Asking an LLM to "infer from the prose whether the answer was
grounded" throws away an oracle that is sitting right there in the trace.

My recommendation, in one sentence: **replace the primary evaluator with a deterministic
grounding verifier driven by a small declarative spec, collapse the 4-way fuzzy
classification down to one irreducible yes/no judgment, and demote the LLM judge to (a) a
fallback for agents with no structured tool oracle and (b) a continuously-calibrated second
opinion whose accuracy you actually measure against the deterministic oracle.**

That last clause is the real answer to *"how do you know the judge is correct?"* — you stop
asserting it and start **measuring** it, against something that can't hand-wave.

And I found something concrete while reading: **the current 100%-accuracy self-eval number
does not measure the code path that runs in production.** Details in §5.

---

## 2. What Cassandra actually evaluates today

The pipeline (`cassandra/loop_agent.py:SupervisionPipeline.run_once`) threads one `Incident`
through 9 stages. Six of them make an LLM-as-judge call:

| # | Call site | Question the judge is asked | Sees tool results? | Temp |
|---|-----------|------------------------------|--------------------|------|
| 1 | `Diagnostician.judge` (`diagnostician.py:65`) | classify `hallucination / tool_failure / prompt_drift / ok` + confidence | **production path: no** / selfeval path: yes | 0.0 |
| 2 | `Evaluator._judge` (`evaluator.py:56`) | did the answer pass this eval case? | **no** | 0.2 |
| 3 | `TraceReplay` judge (`replay.py:43`) | is the original failure now fixed? | no | 0.2 |
| 4 | `RedTeam._judge` (`redteam.py:43`) | did this attack pass? | no | 0.2 |
| 5 | `gate.run_gate` (`gate.py:62`) | CI: does the prompt clear the pass-rate bar? (reuses #2's judge) | no | 0.2 |
| 6 | `SelfEvaluator` (`selfeval.py:52`) | meta: was the *Diagnostician* right vs. labeled traps? (reuses #1) | **yes (HTTP path)** | 0.0 |

### What "correct" means here

The supervised "Patient" (ShopBot, `patient/`) is a **closed-world** domain. Its two tools
return structured JSON with known fields:

- `get_refund_policy(region) → {found, region, policy}` — real data exists only for `US`, `UK`
  (`patient/tools.py:12`).
- `lookup_order(order_id) → {found, order_id, status, carrier, eta}` — `A1002`/`A1003` exist
  but return `carrier: null, eta: null` (`patient/tools.py:17`).

So "correct behavior" has a precise, mechanical definition: **every concrete factual claim
in the answer must be supported by a *successful* tool result; otherwise the agent must
decline/escalate.** The fragile prompt (`patient/agent.py:32`) deliberately tells the model
to do the opposite — fabricate when a tool returns nothing — which is the entire failure
Cassandra exists to catch.

The four failure classes map almost 1:1 onto structural properties of the tool ledger:

| Class | Structural signature in the tool ledger |
|-------|------------------------------------------|
| `hallucination` | answer asserts a policy/fact, but the relevant tool returned `found:false` (or was never called) |
| `tool_failure` | answer asserts a lookup field (carrier/eta), but the tool returned `found:true` **with that field null** |
| `prompt_drift` | answer abandons role/format (poem, pirate speak) — independent of tools |
| `ok` | every concrete claim is backed by a successful tool result, **or** the answer honestly declines |

---

## 3. The core realization

Look at that table again. **Three of the four classes are decided by reading structured
JSON, not by reading prose.** The only thing that genuinely requires natural-language
understanding is a single sub-question:

> **Did the answer assert a concrete fact, or did it honestly decline?**

Everything else — *which* class, *which* field, *which* tool — is bookkeeping over the tool
ledger. The current design asks an LLM to re-derive, from fluent prose, information that is
already present in structured form in the same trace. That is the textbook definition of
using a judge as a crutch.

This reframes the whole problem. Instead of *"is this a reliable 4-way classifier?"* the
question becomes *"can I detect an ungrounded concrete claim?"* — and in a closed-world
domain with structured tool outputs, **claim-vs-grounding is a set-membership check**:

```
unsupported(answer, ledger) :=
    answer contains a concrete claim about field F
    AND there is no successful tool result in `ledger` whose F is present & non-null
```

That is deterministic, reproducible, free, instant, and **auditable** — it can cite the exact
tool call that does (or doesn't) support each claim. An LLM judge can do none of those four
things reliably.

> **The honest caveat (so I'm not overselling).** Deterministic grounding works *here*
> because the tools return **structured** data with **known** fields. The hard, irreducible
> NL residual is "concrete claim vs. honest decline," and the *open-domain* version of
> grounding (claims against free-text retrieved documents) is genuinely an NLI/judge problem.
> So the thesis is not "LLM judges are useless." It is: **for structured-tool agents, the
> structured oracle should be primary and the judge should be the calibrated exception, not
> the default.** §7 says exactly where the judge keeps earning its keep.

---

## 4. What serious teams do (research grounding)

The external consensus lines up with the above almost exactly:

- **Default to code-based/deterministic graders when there is an objectively correct
  answer.** Microsoft, Databricks, and AWS Bedrock AgentCore all describe a *hybrid*: code
  scorers for verifiable facts + format + tool-trajectory assertions, LLM-as-judge reserved
  for *genuinely subjective* assessment. "An LLM evaluator cannot reliably confirm that a
  specific figure appears verbatim… custom code is faster, cheaper, and more reliable for
  deterministic checks."
- **LLM judges have measured, systematic blind spots.** A judge's headline "agreement with
  humans" is not the same as *recall of real defects*; judges catch turn-local issues but
  miss cross-turn/state issues, drift under prompt-wording and formatting perturbations, and
  degrade badly when moved from binary to multi-level ordinal scoring. Multi-level *is* what
  Cassandra asks of its judge (4 classes + a `[0,1]` confidence).
- **You validate a judge by treating it as a classifier with a ground-truth set** —
  precision / recall / F1 / confusion against labels, ideally a "jury" of multiple models to
  dampen single-model bias. That is meta-evaluation, and it is the only defensible answer to
  "how do you know the judge is right."

Strategically this also *aligns with the Arize track*: groundedness / faithfulness /
hallucination evals are core to how Phoenix frames LLM evaluation, and a deterministic
grounding oracle + a calibrated judge is a more sophisticated version of exactly that story —
not a departure from it.

Sources are listed at the bottom (§11).

---

## 5. What's actually wrong today (be honest)

These are findings from reading the code, ordered by how much they undermine the
"defensible evaluation" goal.

### F1 — The self-eval measures a *different code path* than production. ⚠️ biggest issue
The single most important fix this project ever made was "plumb tool results into the judge"
(18% → 100% diagnostic accuracy, per `SYSTEM_DESIGN.md §10`). But that fix only reaches the
judge on the **self-eval HTTP path**: `selfeval.py:42` reads `tool_calls` straight from the
Patient's `/chat` response and forwards them to `judge()`.

The **production path does not.** `normalize_span` sets
`tool_calls = raw.get("tool_calls", [])` (`phoenix_mcp.py:251`) — but the Patient records its
tools as the span *attribute* `tool.calls` nested inside `attributes` (`patient/agent.py:209`),
not as a top-level `tool_calls` key. Then `Diagnostician.diagnose` reads
`span.tool_calls or span.raw.get("tool.calls")` (`diagnostician.py:86`) — both look at the
**top level** of the raw span, where `tool.calls` does not live (it's under
`raw["attributes"]`). Net effect: **in production, the Diagnostician judges with no tool
results.**

Consequence: the reported **100% trap-suite accuracy is an artifact of the self-eval
harness, not a measurement of what runs in prod.** The canonical Germany hallucination still
gets caught (absence-of-grounding is visible from the output alone), which is why the demo
looks fine — but `tool_failure` (needs to *see* the null carrier field) and `ok`
discrimination (the original 18% over-flagging problem) are almost certainly still broken on
the live pipeline, and nobody is measuring it. **This is the "how do you know the judge is
correct" problem in its most literal form: the validation you have is validating the wrong
thing.**

### F2 — Trap labels are attached to *inputs*, not to *(input, output, tools)* triples
`traps.py` labels a *message* with the failure class a correct diagnosis "must" assign. But
the Patient runs at `temperature=0.4` (`patient/agent.py:176,257`), so the same input can
produce a fabrication on one run and an honest "I couldn't find that" on the next. When the
Patient happens to behave well, the *correct* verdict is `ok` — but it's scored against the
fixed label `hallucination` and marked **wrong**. The ground truth is mislocated: a failure
label belongs on what the agent *did*, not on what it was *asked*. This silently caps
achievable accuracy and injects noise into the one metric meant to establish trust.

### F3 — The headline eval metric is broken (and the team already noticed)
The 06-11 session note records baseline **12%** vs candidate **12%** (Δ +0%) while the
**replay says FIXED** on the same incident. The generated postmortem
(`reports/inc-U3BhbjozMDE3.md`) shows the same contradiction: the after-answer clearly
declines correctly, yet the pass-rate delta is zero. Why: `Evaluator._judge` (a) never sees
tool results and (b) grades the live answer against the Synthesizer's free-text
`expected_answer`, which may itself be a *concrete policy* — so a correctly-declining
candidate is judged a failure. The note's own mitigation ("lead with the replay verdict,
treat the tables as supporting texture") is an admission that **the flagship quantitative
metric is not currently trustworthy.** A deterministic grounding verifier would score the
fabricating baseline ≈0% and the declining candidate ≈100% — i.e. it would *recover the true
signal the replay already shows.*

### F4 — "Determinism" is overstated
`SYSTEM_DESIGN.md` says verdicts are deterministic at `temperature=0`. Two caveats: (a) only
the Diagnostician passes `temp=0`; the evaluator/replay/redteam judges use the `0.2` default
(`llm.py:74`); (b) `temperature=0` does not make an LLM deterministic — Gemini/Vertex in
particular vary run-to-run. So "the same turn gets the same verdict every run" is aspiration,
not guarantee. A code-based grounding check *is* actually deterministic.

### F5 — The labeled set is tiny (11 traps)
Even setting F1/F2 aside, 11 cases (4/2/2/3 across classes) cannot support a credible
precision/recall claim per class. You can't defend "the judge is reliable" on 2 `tool_failure`
examples.

---

## 6. Proposed architecture — the **Grounded Verifier**

A four-layer design. Layers 0–1 are the new deterministic core; layer 2 is the demoted,
calibrated judge; layer 3 is the meta-eval that makes the whole thing defensible.

```
            ┌─────────────────────────────────────────────────────────────┐
  trace ──▶ │ L0  Telemetry oracle: extract the structured tool ledger     │
            │     reliably from the span (fix normalize_span)              │
            └───────────────┬─────────────────────────────────────────────┘
                            ▼
            ┌─────────────────────────────────────────────────────────────┐
            │ L1  GroundingChecker(spec): deterministic verdict from the   │
            │     ledger + claim/decline detection. Cites the exact tool   │
            │     call. Reproducible. This is PRIMARY.                      │
            └───────────────┬─────────────────────────────────────────────┘
                            │  abstains? (no spec, or genuinely ambiguous NL)
                            ▼
            ┌─────────────────────────────────────────────────────────────┐
            │ L2  LLM judge (narrowed): answers ONE boolean sub-question    │
            │     ("concrete unsupported claim? y/n") + a cited span.       │
            │     Fallback for agents with no structured oracle.            │
            └───────────────┬─────────────────────────────────────────────┘
                            ▼
            ┌─────────────────────────────────────────────────────────────┐
            │ L3  Meta-eval harness: continuously scores L2 vs L1 (the      │
            │     oracle) → precision/recall/F1/confusion. Trust the judge  │
            │     only within measured bounds. Gate releases on it.         │
            └─────────────────────────────────────────────────────────────┘
```

### L0 — Telemetry oracle (prerequisite; fixes F1)
Make `normalize_span` extract the structured tool ledger from `attributes["tool.calls"]`
(and the OpenInference `tool`/`llm.tool_calls` shapes) into `SpanRecord.tool_calls`, so the
**production** judge/verifier sees the same data the self-eval path already does. Without
this, nothing downstream is trustworthy. Low effort, high leverage. Add a regression test
that feeds a realistic Phoenix span (tools nested under `attributes`) through the *Watcher →
Diagnostician* path and asserts the ledger arrives non-empty.

### L1 — Deterministic `GroundingChecker` driven by a declarative `GroundingSpec`
A new, pure, side-effect-free module. The spec is the **per-agent unit of configuration** —
tiny and fully known for ShopBot:

```python
# illustrative, not final
GroundingSpec(
  lookups=[
    LookupRule(tool="get_refund_policy",
               success=lambda r: r.get("found") is True,
               supports_claim="refund_policy",      # answer may state a policy only if found
               on_missing="hallucination"),         # claim w/o success → hallucination
    LookupRule(tool="lookup_order",
               success=lambda r: r.get("found") is True,
               fields={"carrier", "eta"},            # may state these only if non-null
               on_null_field="tool_failure"),        # claim about a null field → tool_failure
  ],
  decline_markers=["couldn't find","unavailable","can't provide","contact support",
                   "don't have","unable to","not available"],
  claim_extractors={ "refund_policy": <regex: \d+\s*(day|week|month) in refund context>,
                     "carrier": <known carriers/regex>, "eta": <date regex> },
  role_markers=[...],                                # for prompt_drift / format checks
)
```

Given `(answer, tool_ledger, spec)` the checker returns a **structured** `GroundingVerdict`:
the failure class *derived by rule*, plus the evidence (which tool, which field, which
matched claim span). It also returns `abstain=True` when the spec can't resolve the case
(e.g. a claim type it has no extractor for) so L2 can take over rather than guess.

Crucial design choices:
- **No pre-baked "expected answer" is needed for grounding failures.** Run the probe through
  the agent, capture the *runtime* tool ledger, and the spec decides pass/fail directly. This
  deletes the "is the synthesized `expected_answer` even right?" doubt that breaks F3.
- **The spec is what keeps Cassandra agent-agnostic.** ShopBot's spec is bundled; a
  third-party operator writes a small spec (or points at one) the same way they already point
  `BASELINE_PROMPT_FILE` at their prompt. No spec → fall through to L2.
- The checker is trivially unit-testable with no LLM and no network — the opposite of the
  current judge.

### L2 — The LLM judge, demoted and narrowed
Keep a judge, but change its job and its status:
- **One boolean, not a 4-way label.** Ask only the irreducible NL question: *"Does this
  sentence assert a specific <field> value? yes/no,"* and *"Is this an honest decline?
  yes/no."* Narrow, checkable questions are where judges are most reliable (binary >> ordinal,
  per the research). The failure *class* is still assigned structurally by L1 from the
  ledger, not by the judge.
- **Require a citation.** The judge must point at the answer span it's claiming is
  ungrounded; ungrounded-but-uncited verdicts are discarded. This makes its output
  auditable.
- **It is the fallback, not the default** — used when L1 abstains or no spec exists (the
  truly generic / open-domain agent).
- Consider a small **jury** (2–3 model calls, majority vote) for the residual to damp
  single-model bias, but only on the cases L1 couldn't decide — cheap because L1 already
  handled the bulk.

### L3 — Meta-eval harness (this is what makes it *defensible*)
This is the upgraded, honest version of today's `selfeval`. It exists to answer "how do you
know the judge is correct" with numbers:
- **Ground truth = the deterministic oracle (L1)** on the closed domain, *plus* a
  hand-audited slice. Because L1 is deterministic and inspectable, it is a legitimate
  yardstick where a spec exists.
- For each labeled `(input, output, tools)` **triple** (fixing F2 — label the behavior, not
  the input; capture outputs at the temperature production uses), run L2 and compute
  **agreement, precision, recall, F1 per class, and the confusion matrix** — not just one
  accuracy number.
- **Run it on the production path** (fixing F1): the harness must drive Watcher →
  Diagnostician with spans shaped like real Phoenix spans, so the number it reports is the
  number that ships.
- **Gate on it.** The CI gate (`gate.py`) becomes: deterministic grounding pass-rate as the
  hard metric, and a *judge-vs-oracle agreement floor* as a second gate — if the judge drifts
  below its measured precision, the build fails. Prompts are code; so is the judge.

### What changes in the pipeline
- **Diagnostician**: L1 first; class is structural; L2 only on abstain. Annotation now also
  records *which tool result* justified the verdict (stronger Phoenix write-back).
- **Evaluator / RedTeam / Replay / Gate**: replace the prose judge with the grounding
  verifier as the pass/fail oracle. This is what turns the broken 12%/12% into a real,
  reproducible before/after delta and makes the headline metric trustworthy again.
- **Synthesizer**: keep generating diverse probes, but it no longer has to produce a
  trustworthy `expected_answer` — it just needs inputs that *exercise the missing-data path*
  (e.g. regions with no policy, orders with null fields). The runtime ledger is the oracle.

---

## 7. Where the LLM judge genuinely belongs (and how to trust it there)

I'm not proposing to delete the judge. It earns its place when there is **no structured
oracle**:

1. **Open-domain / free-text grounding.** An agent whose "facts" come from retrieved web/doc
   text has no `{found: bool}` to check against. There, grounding = entailment of each claim
   by a source — partly automatable with NLI, but with a real judgment residual.
2. **Subjective quality** — tone, helpfulness, format niceness. Cassandra mostly doesn't
   evaluate these today, which is *why* it's such a good deterministic-verifier candidate; if
   it grows to, that's judge territory.
3. **Generic third-party agents** the operator hasn't written a `GroundingSpec` for. The
   judge is the zero-config path; the spec is the high-trust upgrade.

To make the judge trustworthy in those cases: narrow each call to a single binary/cited
sub-question; use a jury; and **publish its measured precision/recall from L3** so a reader
knows the error bars instead of taking "LLM-as-judge" on faith. A judge with a known,
displayed 0.91 precision on `tool_failure` is defensible; a judge asserted to be "100%
accurate" via a harness that tests the wrong path is not.

---

## 8. What's missing in the codebase (plainly)

To build §6 you would need to **create**, not just edit:

1. **A reliable structured tool ledger in the production path** — `normalize_span` does not
   currently surface `attributes["tool.calls"]`. (Prerequisite; small.)
2. **The `GroundingSpec` / `GroundingChecker` abstraction** — does not exist. New module +
   the bundled ShopBot spec + the generic fallback contract.
3. **Behavior-labeled eval data** — today's labels are on inputs (F2) and there are only 11
   (F5). You'd need a captured set of `(input, output, tools)` triples, ideally
   auto-harvested by replaying inputs and labeling via L1, with a hand-audited subset.
4. **A real meta-eval module** — today's `selfeval` reports a single accuracy number on the
   wrong path. You'd need per-class precision/recall/F1, confusion, the production path, and a
   judge-vs-oracle agreement metric.
5. **A second CI gate** on judge-vs-oracle agreement (extends `gate.py`).
6. **Honest docs** — `SYSTEM_DESIGN.md §7/§10` and the README claim "100% accuracy" and
   "deterministic"; both need the caveats from §5 once this lands.

None of this requires new infrastructure or services — it's all local, testable Python plus a
spec file. That's the good news: the data and structure you need (structured tool outputs)
already exist; they're just not being *used* as the oracle.

---

## 9. Suggested phasing (for when you approve)

1. **Fix L0 + add the production-path test** (proves/【dis】proves F1 empirically). Smallest
   change, biggest credibility payoff — it tells you the *real* current accuracy.
2. **Build L1 `GroundingChecker` + ShopBot spec**, unit-tested offline.
3. **Swap the Evaluator/Replay/RedTeam/Gate pass-fail oracle to L1** → recover a real
   baseline-vs-candidate delta (fixes F3).
4. **Re-label traps as triples + expand**, build the **L3 meta-eval** (precision/recall on the
   production path), and demote the Diagnostician's judge to abstain-only (fixes F2/F4/F5).
5. **Add the judge-vs-oracle CI gate** and update docs honestly.

Each step is independently shippable and independently improves defensibility.

---

## 10. Counterarguments to my own proposal (so you can push back)

- *"Rule-based claim extraction is brittle."* True — regexes for "30-day refund" / carrier
  names are ShopBot-specific and will miss paraphrases. Mitigations: the spec confines
  brittleness to one small, reviewable file; L1 *abstains* (rather than guessing) into the
  judge when its extractors don't match; and L3 measures exactly how often abstain happens.
  Brittleness becomes a *measured* quantity, not a hidden risk.
- *"This only works because ShopBot is a toy closed world."* Partly fair — and it's the honest
  reason the deterministic approach is so strong *here*. The generalization story is the
  `GroundingSpec`: structured-tool agents (most enterprise support/ops agents) get the
  deterministic path; truly open-domain agents fall back to the calibrated judge. The design
  degrades gracefully rather than pretending one size fits all.
- *"It's more moving parts than one judge call."* Yes, but they're *deterministic, testable*
  parts replacing a *stochastic, untestable* one. The current single judge call is simpler to
  write and impossible to trust; that trade is the whole point of the exercise.

---

## 11. Sources

- [Evaluating AI Agents: Can LLM-as-a-Judge Evaluators Be Trusted? — Microsoft](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/evaluating-ai-agents-can-llm%E2%80%91as%E2%80%91a%E2%80%91judge-evaluators-be-trusted/4480110)
- [Catching One in Five: LLM-as-Judge Blind Spots in Production Multi-Turn Agents (arXiv)](https://arxiv.org/html/2606.10315)
- [Judge Reliability Harness: Stress Testing the Reliability of LLM Judges (arXiv)](https://arxiv.org/pdf/2603.05399)
- [A Survey on LLM-as-a-Judge (arXiv)](https://arxiv.org/pdf/2411.15594)
- [What is AI Agent Evaluation? — Databricks](https://www.databricks.com/blog/what-is-agent-evaluation)
- [Build reliable AI agents with Amazon Bedrock AgentCore Evaluations — AWS](https://aws.amazon.com/blogs/machine-learning/build-reliable-ai-agents-with-amazon-bedrock-agentcore-evaluations/)
- [Common evaluation approaches — Microsoft Learn](https://learn.microsoft.com/en-us/agents/architecture/common-evaluation-approaches)
- [Agent Evaluation Readiness Checklist — LangChain](https://www.langchain.com/blog/agent-evaluation-readiness-checklist)
- [Agent Evaluation: A Detailed Guide — Cameron R. Wolfe](https://cameronrwolfe.substack.com/p/agent-evals)
- [LLM-as-a-Judge — Wikipedia](https://en.wikipedia.org/wiki/LLM-as-a-Judge)
