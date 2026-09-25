# Task 0: how often does a real agent assert a value its tools never returned?

> **Status:** measurement, 2026-08-21.
> This is task 0 of the framework-extraction plan, the cheapest available falsification of the product thesis, to be run *before* the ~30 h
> `grounding.py` rewrite. It has now been run. **The result does not support the thesis.**
>
> **Reproduce** (no API keys, no LLM spend, ~50 MB download, runs in about a minute):
>
> ```bash
> mkdir -p /tmp/tau && cd /tmp/tau
> for f in gpt-4o-airline gpt-4o-retail sonnet-35-new-airline sonnet-35-new-retail; do
>   curl -sLO "https://raw.githubusercontent.com/sierra-research/tau-bench/main/historical_trajectories/$f.json"
> done
> export TAU_TRAJECTORY_DIR=/tmp/tau
> python scripts/task0_measure_grounding.py     # the base-rate numbers in §4
> python scripts/task0_bound_addressable.py     # the 87.6% in §4
> ```

---

## 1. The answer, up front

On 1,980 real tool-using agent trajectories:

| Question | Answer |
|---|---|
| Do agents assert identifiers no tool returned? | **Essentially never.** Every one of the 39 candidate cases was a false positive on inspection |
| Do agents assert *numbers* not in the ledger? | Often — 7.96% of values — but **82.4% is arithmetic** on ledger values, and the rest is policy constants and reformatting |
| Does a grounding anomaly predict task failure? | **Barely.** Precision 44.8% against a 40.3% base rate. +4.5pp over guessing |
| What share of real failures involves any grounding anomaly? | **12.4%.** The other **87.6% of failures are invisible to any value-grounding check** |

**The failure Cassandra is built to catch is not the failure these agents actually have.**

## 2. Corpus

`sierra-research/tau-bench` `historical_trajectories/` — the benchmark's own published runs.

| File | Trajectories |
|---|---|
| `gpt-4o-airline.json` | 200 |
| `gpt-4o-retail.json` | 460 |
| `sonnet-35-new-airline.json` | 400 |
| `sonnet-35-new-retail.json` | 920 |
| **Total** | **1,980** (12,909 claim-bearing assistant turns, 29,381 concrete values) |

Chosen because each trajectory carries the full message sequence — tool calls, tool results, and
the agent's natural-language replies — **plus a programmatic `reward`** computed against the
environment's final database state. That reward is text-independent ground truth, which is what
makes the correlation analysis in §4 possible at all. This is not a synthetic corpus and it is not
ShopBot; measuring against our own demo would have been circular.

## 3. Method

Walk each trajectory in order, maintaining an **evidence set**: every value appearing in a tool
result, a tool call's arguments, a user message, or the system prompt. For each assistant reply,
extract high-precision typed values (money, ISO dates, `snake_case_1234567` ids, flight codes,
order/reservation codes) and ask whether each is in the evidence set.

Deliberately excluded: bare small integers, percentages, times. They generate false positives from
list numbering and arithmetic, and an inflated number here would be worse than no number.

Two corrections were required before the output meant anything, and both are findings in their own
right (§5).

## 4. Results

```
concrete values asserted              29,381
not literally in the ledger            2,339   (7.96%)
  of which arithmetic on ledger vals   1,928   (82.4% of those)
  residual                               411   (1.40% of values)

turns flagged, naive check             1,653   (12.81% of claim turns)
turns flagged, arithmetic-aware          311   (2.41%)
```

### The residual does not survive inspection

All 39 non-money residual turns were read individually. Every one is a false positive, in three
classes:

1. **Format examples.** *"It should start with a '#' symbol, like '#W0000000'"*, *"a 6-character
   code like ABC123"*. The agent explaining an ID format, not claiming one. Most common class.
2. **User-supplied values, reformatted.** A date of birth given in prose as "March 22, 1992" and
   written back as `1992-03-22`. Present in the conversation, absent in that surface form.
3. **Substring artefacts.** `card_3563913` extracted out of `credit_card_3563913`.

The money residual is the same story: the recurring `$30` is the travel-insurance price stated in
the **system prompt policy**, and larger values are multi-step derivations the bounded arithmetic
check missed.

**Hard fabrication — an identifier from nowhere — occurred approximately zero times in 29,381
asserted values.**

### Correlation with ground truth

```
trajectories                    1,980
failed the task                   797   (40.3%)

FAILED with any grounding anomaly  99/797   (12.4%)
PASSED with any grounding anomaly 122/1,183 (10.3%)

as an alert: precision 44.8%, recall 12.4%   (base rate 40.3%)
```

A detector that fires on 10.3% of *successful* trajectories and 12.4% of failed ones is not
separating anything. **87.6% of real failures show no grounding anomaly at all** — every value the
agent asserted traced back to its tools, and the task still failed.

## 5. Two method findings worth keeping

Both bear directly on §4.3 of the extraction plan, and neither is in it today.

1. **Most numeric claims are derived, not quoted.** 82.4% of apparent violations were sums,
   differences, or per-unit splits of ledger values: *"$5 remaining"* is $255 − $250, *"$239
   total"* is $109 + $130. A verifier that asks only "is this value in the ledger" flags every
   correct total. The plan's `numeric-coherence` layer must handle **derivation**, not just unit
   canonicalisation and tolerance — otherwise its false-positive rate makes it unusable regardless
   of how correct its equality check is.
2. **Format normalisation is load-bearing, and silent when wrong.** The first run reported a 13%
   anomaly rate purely because one regex used a trailing `\b` and therefore never matched the date
   inside `2024-05-01T15:00:00`. Tool-returned dates never entered the evidence set, so every
   correctly-quoted date was flagged. A spec author will hit this constantly and get no signal that
   it happened — which compounds the already-flagged risk that spec authoring is the adoption
   blocker.

## 6. Threats to this conclusion

Stated plainly, because they are the grounds on which it could be wrong.

- **It does not test misattribution.** This measures *absence from the ledger*. Cassandra's
  sharper claim is that an agent quotes order A's carrier when answering about order B — where
  **both values are in the ledger** and this method is blind. That case needs field-level
  alignment, i.e. a spec, and remains untested. It is also exactly the defect flagged at
  `grounding.py:77-78` (calls matched by tool name only). **This is the one live hypothesis left.**
- **tau-bench failures are mostly procedural.** These agents fail by not following the airline's
  policy, not by lying about data. A domain where the answer *is* the deliverable — claims
  adjudication, order status, billing — could distribute differently.
- **Strong models, clean environment.** GPT-4o and Sonnet 3.5 on a well-scoped benchmark with a
  good system prompt. A weaker model on a messier domain may fabricate more.
- **Deliberately conservative extractors.** Broader extraction would raise recall and, on the
  evidence of §4, precision would fall faster.

## 7. Independent corroboration

[*From Confident Closing to Silent Failure: Characterizing False Success in LLM Agents*](https://arxiv.org/abs/2606.09863)
(arXiv 2606.09863) analysed 9,876 tau2-bench and 1,879 AppWorld trajectories. It reports:

- False success — asserting completion when environment state says otherwise — is **45–48% of
  failures** in single-control tau2-bench domains, 75.8% in AppWorld self-assessment.
- **LLM judges cannot detect it**: no configuration of 5 judges × 5 prompt strategies exceeded
  **AUROC 0.65** on tau2-bench, and 0.54 on AppWorld — near chance.
- A **TF-IDF detector reaches AUROC 0.83 / 0.95**, recovering 4–8× more false successes than the
  best judge at 3,300× lower latency.

Read carefully, this both helps and hurts:

- **Helps:** it independently confirms the premise that LLM judges are near-useless for this, which
  is the assumption the whole product rests on.
- **Hurts, more:** the dominant failure is *false claims of completion*, not *fabricated values* —
  consistent with §4 here. And a **bag-of-words baseline already solves it at 0.83–0.95 AUROC**,
  with no spec to author. Our differentiator is a spec-dependent verifier aimed at a rarer failure,
  competing against something with no adoption cost at all.

## 8. What this implies

1. **Do not start the 30 h `grounding.py` rewrite on the current premise.** It fixes verdicts that
   are real defects, but on this evidence it is not fixing a frequent or commercially sharp failure.
2. **The one surviving hypothesis is misattribution** — wrong-but-present values. Test it next, and
   it is cheap: hand-author a `GroundingSpec` for the tau-bench retail domain, run field-level
   alignment over the same 1,980 trajectories, and count. A day or two, not 30 h. If misattribution
   is also rare, the deterministic-grounding thesis is finished and should be dropped rather than
   rebuilt.
3. **The adjacent, larger problem is task-completion claims**, which is what the 87.6% is made of
   and what the paper measures. If there is a product here, it is closer to "did the agent actually
   do what it said" than "did the agent quote the right value" — a different verifier, a different
   spec, and a cheaper baseline to beat.
4. **The backtest-report go-to-market survives, with different contents.** Selling a team a report
   on their own traces is still the right wedge; §4 says the report should not lead with grounding
   verdicts, because on this evidence it would be a near-empty report.
