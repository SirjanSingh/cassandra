# Cassandra × ZombieE — RL Merge Proposal

> **Status:** proposal / discussion doc for partner review (2026-07-02). **No application code
> was changed** producing this — it is a strategy artifact only.
> **What it is:** a written-down version of a brainstorming session on whether/how to fold an
> RL fine-tuning project ("ZombieE") into Cassandra to produce a *sellable* product, and which
> shape earns the best money with the least risk.
> **Reads with:** [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md) (independence + business model),
> [`MARKET_AND_ALTERNATIVES.md`](MARKET_AND_ALTERNATIVES.md) (competition), and
> [`EVAL_PLAN.md`](../EVAL_PLAN.md) (the deterministic grounding verifier — the hinge this
> whole proposal turns on).

---

## 0. TL;DR (the opinionated version)

We looked at whether to merge **ZombieE** (a GRPO/LoRA RL fine-tuning project — Qwen2.5-3B on a
5-agent survival game, with a hand-built multi-rubric reward and a matched-baseline eval
harness) into **Cassandra** (the agent-reliability product) to make money.

**Conclusion:** don't merge the codebases, and don't let RL derail Cassandra's CI-gate wedge.
Instead, take the *one* thing ZombieE is genuinely good at — designing and training against
**verifiable reward signals** — and use it to power a new Cassandra product surface:

> **A private, verifiable, self-expanding benchmark of your own agent — grown by an RL
> adversary, graded by Cassandra's deterministic oracle.**

- **Cassandra** already manufactures the scarce thing RL is starving for: a deterministic,
  auditable pass/fail verdict (`grounding.py` / `oracle.py`) plus real failure datasets mined
  from production traffic (`synthesizer.py`). That is a *verifiable reward* in the exact sense
  the frontier RL market means it.
- **ZombieE's RL skill** becomes the engine that *grows* the benchmark: an RL-trained adversary
  whose reward is Cassandra's verifier, actively hunting for failure cases faster than
  production surfaces them.
- **Business:** sell it eval-first (lowest friction, Cassandra's existing buyer and brand),
  with a natural upsell to RL fine-tuning later because every case is already an
  `(environment + verifiable reward)`.

This keeps Cassandra's moat, buyer, and sequencing intact, rides the "verifiable rewards" wave
without fighting the data-foundry incumbents, and gives RL a real job instead of a decorative
one.

---

## 1. The two projects (context for the reviewer)

| | **Cassandra** | **ZombieE (v2)** |
|---|---|---|
| What it is | Meta-agent that supervises other LLM agents: detect → diagnose → synthesize regression dataset → patch prompt → verify → gate | GRPO fine-tuning of Qwen2.5-3B-Instruct (LoRA) on a 5-agent social-deduction survival game |
| Maturity | **Near-product.** Working code, 66 passing tests, deterministic grounding verifier shipped, full product/market/business plans | **Portfolio project.** Strong RL demonstration, honest 4-run debugging arc, no buyer |
| Core asset | Deterministic, telemetry-grounded verification (the moat); the incident→dataset flywheel | RL/reward-design skill: GRPO, LoRA on constrained GPUs, multi-rubric reward, matched-baseline eval |
| Weakness | Fixes agents only by **prompt patching** | The reward was repeatedly **gameable** (scan-spam exploit, heuristic ceiling) — reward design is the hard part |

**The key observation:** ZombieE's biggest failure mode (a gameable reward) is *exactly* the
problem Cassandra's deterministic verifier solves. That complementarity is the whole basis for
this proposal.

---

## 2. Ideas we considered and rejected (so you can push back)

We deliberately generated several merge shapes and killed the weak ones. Ranked, with honest
verdicts:

### 2.1 ❌ Literally merge the two codebases
Different stacks entirely (Cassandra: FastAPI + telemetry + LiteLLM/Vertex; ZombieE: PyTorch +
GRPO + Docker + V100). Nothing to share. A code merge buys nothing. **Rejected.**

### 2.2 🟡 RLVR remediation tier — fine-tune the customer's model to fix failures
Cassandra mines a failure → GRPO fine-tunes the customer's open-weight model so the failure is
fixed in the *weights*, not just the prompt. Verified by the same deterministic oracle.
- Genuinely differentiated (no one in Cassandra's Ring-3 map does weight-level remediation).
- **But:** open-weights only; needs GPUs; slower/riskier than prompt patching; cuts against
  Cassandra's low-risk brand. **Verdict: keep as a far-future differentiator, not a target.**

### 2.3 💰 Verifiable-environment factory — sell RL environments/rewards
Turn a customer's traffic into RL training environments + reward functions. Rides the hottest
part of the market. **But** the *naive* version (sell generic envs to frontier labs) is a trap
— see §3. The *refined* version (private envs for the agent-owner) is what survived and became
this proposal.

### 2.4 ⭐ RL red-teamer — an adversary trained to break the customer's agent
An RL policy rewarded (+1) every time it provokes a failure the deterministic verifier catches.
Same buyer, same brand, extends `redteam.py` from static attacks to a *learning* attacker.
**This is the strongest RL-at-the-base idea, and it fuses with 2.3 to form the final product
(§4).**

---

## 3. Market reality check (verified 2026-07-02)

We checked whether the "RL environments" market is real before betting on it. It is — and the
check also told us where *not* to play.

**The market is real and enormous:**
- Anthropic discussed spending **$1B+ on RL environments** in a single year; OpenAI 2026 R&D
  compute ~$19B.
- The paradigm is **RL post-training on verifiable rewards** ("RL works best when rewards are
  verifiable") — precisely what Cassandra's grounding verifier produces.
- Heavy funding: **Mercor** ($10B valuation, Oct 2025), **Surge** ($1.2B revenue, added an
  RL-environments division), **Mechanize** ($500k salaries, Anthropic partnership),
  **Prime Intellect** (Environments Hub, Karpathy-backed). 35+ startups.

**But the naive version is a trap:**
- Analyst pieces literally titled *"Don't Build an RL Environment Startup"* and *"Who Will Win
  the RL Environment Market"*; consensus is consolidation to **3–5 winners by 2030**.
- Selling *generic* environments to *frontier labs* means fighting Surge/Mercor, who have
  billion-dollar revenue and direct lab relationships. A solo builder loses that fight.

**The wedge that fits us:** don't sell generic envs to labs. Sell **each enterprise a private,
verifiable benchmark of its *own* agent**, derived from its own traffic + a deterministic
verifier — something the incumbents *cannot* produce because they don't have the customer's
traffic or a grounding oracle attached. Different buyer, different product, same wave.

**Sources:**
[TechCrunch](https://techcrunch.com/2025/09/21/silicon-valley-bets-big-on-environments-to-train-ai-agents/) ·
[Epoch AI](https://epoch.ai/gradient-updates/state-of-rl-envs) ·
[Wing VC](https://www.wing.vc/content/who-will-win-the-rl-environment-market--and-why) ·
["Don't Build an RL Env Startup"](https://benanderson.work/blog/dont-build-rl-env-startup/) ·
[SemiAnalysis](https://newsletter.semianalysis.com/p/rl-environments-and-rl-for-science) ·
[AlignList — Top 40 RL env startups](https://alignlist.com/guides/top-40-rl-environments-startups-and-companies)

---

## 4. The proposed product

**"A private, verifiable, self-expanding benchmark of your own agent — grown by an RL
adversary, graded by a deterministic oracle."**

Three parts, each mapping to an existing asset:

1. **The asset (Cassandra flywheel).** Every real production failure becomes a permanent,
   verifiable test case: `incident → GroundingVerdict → dataset`. The customer owns a benchmark
   of *their* agent's actual weak spots. This is the switching cost — a competitor can't
   reproduce a corpus mined from the customer's own traffic.

2. **The engine (ZombieE RL).** Production only surfaces the failures customers happen to hit.
   An **RL-trained adversary** (GRPO/LoRA — ZombieE's exact skillset) whose **reward is the
   deterministic verifier's pass/fail** actively hunts for *new* failure cases and injects them
   into the benchmark. This is textbook **RLVR** — the verifier is the verifiable reward. RL is
   the machine that manufactures hard, pre-verified test cases faster than reality does. It
   extends `redteam.py` from static attacks to a learning attacker.

3. **The money ladder (on-ramp).** Because every case is an `(environment + verifiable reward)`,
   the benchmark you sold as *eval* is already **RL-training-ready**. Upsell path:
   buy the benchmark (eval) → later fine-tune your open-weight model against it (§2.2
   remediation tier) → all on one artifact. Land with the easy sell, grow into the high-value
   one.

### Why it's defensible
- Rides the **verifiable-rewards** wave without fighting Surge/Mercor (different buyer: the
  agent owner, not the lab).
- Keeps Cassandra's brand: the **grade stays deterministic** even though the adversary is RL —
  no "trust the LLM judge" problem.
- No competitor in Cassandra's Ring-3 map (Braintrust, Opik) pairs **an RL adversary** with **a
  deterministic verifier** to grow a **customer-owned** benchmark. The moat is the combination.

---

## 5. How it technically merges with Cassandra

The merge is an **interface + a new module**, not a rewrite. Cassandra already has the seams.

| Cassandra piece (today) | Role in the merged product |
|---|---|
| `cassandra/grounding.py` (`check_grounding`, `GroundingVerdict`, `SHOPBOT_SPEC`) | **The reward function.** Its deterministic pass/fail is the RL reward signal — non-gameable and auditable |
| `cassandra/oracle.py` (`score_case`, `deterministic_verdict`) | The graded oracle the benchmark and the RL loop both call — one source of truth |
| `cassandra/synthesizer.py` | Seeds the benchmark from real incidents; the RL adversary expands beyond it |
| `cassandra/redteam.py` | Becomes the home of the **learning** adversary (static attacks → RL policy) |
| `cassandra/gate.py` | The CI-gate wedge; the benchmark plugs in as the pass/fail suite |
| `cassandra/patient_client.py` (`ask_patient`) | The adversary drives the target agent through this existing contract |
| ZombieE training harness (GRPO/LoRA, `--prefix-actions`, matched-baseline eval) | Ported as a standalone **`Adversary` trainer** that consumes `(target agent, GroundingSpec)` and emits new verified cases |

**Critical validation gate (do not skip):** the RL adversary must demonstrably find failures the
cheap static synthesizer does *not*. If it can't beat the baseline, RL is decoration. ZombieE's
own matched-baseline eval methodology is exactly the tool to prove or disprove this — treat it
as the go/no-go experiment before building the product surface.

---

## 6. Business model

Consistent with Cassandra's existing open-core plan (`PRODUCT_PLAN.md §4`):

- **Buyer:** the team running a customer-facing agent (Cassandra's existing ICP) — **not**
  frontier labs.
- **Wedge:** eval-first. "A private, always-growing, verifiable benchmark of *your* agent."
  Lowest friction; sits on top of the CI-gate wedge Cassandra is already pursuing.
- **Open core (MIT/Apache):** the verifier, the benchmark format, the CI gate, single-node run.
- **Paid (hosted + enterprise):** hosted dashboards, the owned benchmark/dataset store, the RL
  adversary as a managed service, team/RBAC/SSO, and — later — the fine-tuning/remediation tier
  (the open-weights enterprise unlock).
- **Meter on the verb that creates value** — "agents benchmarked" / "verified cases maintained"
  — not raw spans, so we're not reselling storage like the observability incumbents.

---

## 7. Honest risks

1. **The eval market is also crowded** (DeepEval, Braintrust, Opik). The wedge must be the
   *combination* (RL-grown + verifiable + customer-owned), not "another eval tool."
2. **The RL adversary must earn its keep** (see §5 validation gate). Highest technical risk.
3. **Open-weights gate** applies to the *training* upsell (not the eval product) — which is the
   reason to lead with eval.
4. **Scope discipline.** Cassandra's every doc says *narrow, ship the CI-gate wedge, don't let
   the eval re-arch slip*. This proposal must **not** jump ahead of that. It is a Phase-C
   product surface, earned after the wedge lands — not a pivot.
5. **Brand tension.** "We don't ask you to trust a heavy stochastic thing" vs. RL being heavy
   and stochastic. Mitigated by the verifiable-reward framing (the *reward* is deterministic),
   but it must be messaged carefully.

---

## 8. Open decisions for the partner

1. **Is eval-first the right lead**, with RL adversary as the differentiator and fine-tuning as
   a later upsell? (Recommended.)
2. **Run the validation gate first?** Before any product build, run the matched-baseline
   experiment: does an RL adversary find failures the static synthesizer misses? Go/no-go.
3. **Where does the RL adversary live** — inside Cassandra as an optional module, or as a
   separate service Cassandra calls? (Leaning: separate trainer, thin interface.)
4. **Timing vs. the CI-gate wedge** — confirm this stays behind the wedge and the eval
   re-architecture (`EVAL_PLAN.md` B3), not ahead of them.
5. **Naming/branding** for the benchmark product surface.

---

## 9. Suggested sequencing (dependency-ordered; no code yet)

1. **Finish Cassandra's eval re-architecture** (`EVAL_PLAN.md` B3 — meta-eval, judge demotion).
   Prerequisite for any trustworthy reward signal.
2. **Ship the CI-gate wedge** and land design partners (unchanged Cassandra plan).
3. **Run the RL-adversary validation gate** (§5) as a contained experiment using ZombieE's
   matched-baseline harness. Go/no-go on the whole RL angle.
4. **If go:** build the `Adversary` trainer behind a thin interface; wire its reward to
   `oracle.py`; grow a real customer-owned benchmark.
5. **Later:** the RL fine-tuning / remediation upsell for open-weights enterprise customers.

---

*This is a review artifact. No Cassandra application code was changed producing it; the repo's
code state (including the uncommitted B1/B2 grounding-verifier working tree) is exactly as it
was.*
