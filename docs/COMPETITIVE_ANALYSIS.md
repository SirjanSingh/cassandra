# Competitive analysis (2026-11-05)

> Part of the strategy set. Master document: [PRODUCT_VISION_AND_COMPANY_ROADMAP.md](PRODUCT_VISION_AND_COMPANY_ROADMAP.md).
> Supersedes the competitive sections of `docs/archive/MARKET_AND_ALTERNATIVES.md` (June 2026,
> on `feature/nli-and-hindi`). The market has moved a lot since June.

**Rules for this document.** Every fact carries a source and a verification level:

- **Primary**: read on the vendor's own page or an official announcement, today.
- **Press**: reported by named outlets.
- **Aggregator**: third-party pricing sites, which often disagree with each other.

Aggregator prices are directional only. **No market size, customer count or willingness-to-pay figure here
is ours**: where none is cited, none is claimed.

---

## 1. What changed in 2026 (why the June research is stale)

| Event | Date | Verification | Why it matters to us |
|---|---|---|---|
| ClickHouse acquired **Langfuse** (with a $400M Series D) | 2026-01-16 | Press ([SiliconANGLE](https://siliconangle.com/2026/01/16/database-maker-clickhouse-raises-400m-acquires-ai-observability-startup-langfuse/)) | The leading OSS tracing tool is now part of a database company. It stays MIT/self-hostable per reports, but becomes a data-platform feature. |
| OpenAI announced it will acquire **Promptfoo** (OSS evals + red-teaming) | 2026-03-09 | Press ([SiliconANGLE](https://siliconangle.com/2026/03/09/openai-acquire-promptfoo-expand-ai-application-testing-capabilities/), [Built In](https://builtin.com/articles/openai-promptfoo-acquisition-20260310)) | The best-known OSS "test your prompts in CI" tool is now inside a model vendor's agent platform. Validates the category; removes a neutral option. |
| Snyk acquired **Invariant Labs** (agent guardrails + trace analysis) | 2025-06-24 | Primary ([Snyk](https://snyk.io/news/snyk-acquires-invariant-labs-to-accelerate-agentic-ai-security-innovation)) | Rule-based agent trace analysis exists, but it is pointed at *security*, not business correctness. |
| **Raindrop** raised a $15M seed (Lightspeed) as "Sentry for AI agents" | Dec 2025 | Press ([VCA Online](https://www.vcaonline.com/news/2025120102/raindrop-raises-15-million-to-detect-critical-ai-agent-failures/)) | It owns the exact framing in our `POSITIONING.md` ("Sentry for wrong answers"). |
| **Sentry** ships AI agent monitoring on all plans, including the free one | 2026 | Vendor marketing page ([sentry.io/for/ai](https://sentry.io/for/ai/)), not the pricing page | The literal Sentry is in the space, free, with an installed base. |
| **Braintrust** Pro listed at **$249/month**, Starter $0 | Fetched 2026-11-05 | Primary ([braintrust.dev/pricing](https://www.braintrust.dev/pricing)) | Platform pricing is compressing. One aggregator reports a 75% cut in Aug 2026. |
| **LangSmith** Plus at **$39/seat/month** + pay-as-you-go; an "Insights" agent clusters failures on a schedule | 2026 | Official pricing page per [langchain.com/pricing](https://langchain.com/pricing); trace allowances conflict across aggregators | "Automatically find failure patterns in traces" is now a $39 feature. |
| OTel GenAI semantic conventions moved to their own repo (v1.42.0); all `gen_ai.*` attributes are still "Development" | 2026-06/07 | Secondary ([Dash0](https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained), [Greptime](https://www.greptime.com/blogs/2026-05-09-opentelemetry-genai-semantic-conventions)) | `execute_tool` spans are standardising. A vendor-neutral tool-ledger ingest is becoming feasible, but no stable schema exists yet. |
| arXiv 2606.09863: LLM judges detect agent "false success" at AUROC ≤ 0.65 (tau2-bench) / 0.54 (AppWorld); lightweight calibrated detectors do far better | 2026-06 (ICML 2026 listing) | Primary abstract + ICML page ([arXiv](https://arxiv.org/abs/2606.09863), [ICML](https://icml.cc/virtual/2026/77904)). The TF-IDF 0.83/0.95 figure is from the paper per our Task 0 doc; not re-read in full here | Independent support for "LLM-as-judge is not an alarm", the one claim all our own evidence agrees on. |

## 2. The landscape in four rings

### Ring 1: tracing and observability platforms
Crowded and commoditising. Teams already have one of these. **We integrate with them; we don't replace them.**

| Product | What it is | Pricing (verification) | Strength | Weakness relative to our wedge |
|---|---|---|---|---|
| Arize Phoenix / AX | OSS tracing + evals (Phoenix, **Elastic License 2.0**, verified from the [LICENSE](https://github.com/Arize-ai/phoenix/blob/main/LICENSE)); managed AX; "Alyx" assistant | AX Free / Pro ~$50/mo / Enterprise (aggregator; [Capterra](https://www.capterra.com/p/10049394/Arize-AI/), [checkthat.ai](https://checkthat.ai/brands/arize-ai/pricing)). Enterprise median ~$60k/yr per a marketplace (aggregator) | OpenInference standard, big OSS footprint; our current integration target | ELv2 forbids offering Phoenix as a hosted service, so we can never host it. Evals are LLM-judge-centric. They could ship deterministic checks. |
| Langfuse (ClickHouse) | MIT OSS tracing, prompt mgmt, evals | Unit-metered cloud; self-host free (aggregator) | Most-adopted OSS tracer; now well-funded | No opinion on verifying agent behaviour; generic scores |
| LangSmith | LangChain's tracing/eval platform | $39/seat/mo + PAYG (official page as reported) | Huge LangChain installed base; Insights agent | Evaluators are LLM-judge or user code; tied to the LangChain ecosystem in practice |
| Datadog LLM Observability | Enterprise APM extension | Not found | Already in the enterprise; out-of-the-box hallucination eval ([blog](https://www.datadoghq.com/blog/ai/llm-hallucination-detection/)) | That eval is LLM-as-judge, aimed at RAG. Datadog's own blog says faithfulness needs a context to check against. |
| Sentry AI monitoring | Error monitoring + agent tracing (`gen_ai.execute_tool` spans) | All plans incl. free (vendor marketing page) | Developer love, installed base, free | Monitors runtime errors and cost, not semantic correctness |

### Ring 2: evaluation and testing frameworks
Where developers decide how to *grade*. This is where our CLI lives.

| Product | What it is | Pricing (verification) | Notes |
|---|---|---|---|
| Braintrust | Eval platform + **Loop**, an agent that "can run evaluations, generate test cases, and iterate on prompts" (primary, pricing page) | Starter $0, Pro $249/mo, Enterprise custom (**primary**, 2026-11-05) | Loop is the closest shipped analogue to Cassandra's "detect → patch → re-eval" loop, inside a platform teams already pay for. |
| Promptfoo (→ OpenAI) | OSS CLI for evals/red-teaming in CI | OSS free; enterprise | Developer-loved CLI + YAML; what our `gate` resembles. OpenAI said it will keep the OSS project. |
| DeepEval / Confident AI | Apache-2.0 pytest-style eval library + hosted platform | OSS free; hosted tiers conflict across aggregators ($0/$200/$2,000 per [one review](https://ecorpit.com/rag-evaluation-tools-ragas-deepeval-braintrust-giskard-2026/)) | Proof that "pytest for LLMs" distributes well as OSS. Its metrics are mostly LLM-judged. |
| pytest-agentreplay | OSS VCR-style record/replay of model + tool calls for CI ([PyPI](https://pypi.org/project/pytest-agentreplay/)) | Free, v0.1.4 | **Validates the replay gap we found**; tiny project. |

### Ring 3: specialised reliability, hallucination and failure-analysis vendors
Our most direct competitors on the *detection* claim.

| Product | Approach | Pricing (verification) | Our read |
|---|---|---|---|
| Galileo | Luna-2 small evaluation models (3B/8B); claimed ~$0.02/1M tokens and 152 ms (aggregator-reported vendor claims); Insights engine "prescribes fixes"; Protect guardrails | Free tier; enterprise not public (aggregator; Pro $100/mo per a competitor's table, unverified) | Cheap model-based judges at scale. Probabilistic, not evidence-citing. A strong incumbent for "monitor 100% of traffic". |
| Patronus AI | Percival: agent trace debugger, 20+ failure modes, error clustering, prompt-fix suggestions ([docs](https://docs.patronus.ai/docs/percival/percival)); TRAIL benchmark | Not found | Closest to "diagnose → suggest fix". Self-reported TRAIL joint accuracy 0.17 (vs 0.11 baseline), which shows how hard trace diagnosis is. |
| Raindrop | "Sentry for AI agents": detects silent failures (hallucinations, tool misuse, user frustration), root-cause, Slack alerts | Not found; $15M seed (press) | Same buyer, same pitch, already funded and selling. We must not position as "Sentry for agents". |
| Cleanlab TLM | Trust score per output; pay-per-token, rates not public ([docs](https://help.cleanlab.ai/tlm/)) | Not found | Model-agnostic uncertainty score; no tool-ledger reasoning. |
| Invariant (Snyk) | Rule/policy checks over agent traces; guardrails | Part of Snyk | The closest *technical* cousin (rules over traces), pointed at security and policy. Watch it. |

### Ring 4: build-it-yourself
The real default competitor. Every Ring 1–2 platform accepts **custom code scorers**. A competent team can
write `assert tool_result["carrier"] in answer` in an afternoon. Our product has to beat the afternoon, not
just Galileo.

## 3. Why would a developer switch to Cassandra?

**Honest answer: today they wouldn't, and they shouldn't have to switch anything.** Cassandra has no users.
Its only detector is regex-based with known correctness holes (master document §3). Its full pipeline needs
Phoenix, an adapter that exposes a system-prompt override, and 5+ env vars.

The positioning must therefore be **adopt alongside, not instead**. Three claims would make a developer add
Cassandra next to their existing tracer. All three have to be made true:

1. **"Alerts you can trust."** Verdicts are deterministic and cite the tool call, so a flagged turn is
   actionable without a second look. The evidence today:
   - TravelPal held-out: 100% precision (11/11), versus 37–53% for the LLM judge alone;
   - Task 0: 80.4% precision for the swallowed-error check;
   - published: judges at AUROC ≤ 0.65.

   This is the differentiator the incumbents' LLM/SLM judges structurally lack. It is also the claim most
   in need of proof on real logs.
2. **"Five minutes, on your laptop, nothing leaves."**
   - `pip install`, point it at a log export, and get a report.
   - No platform, no account, no LLM by default.
   - Regulated teams can run it before procurement.

   `cassandra scan` already does this. **Missing: the contract has to be generated, not hand-written in regex.**
3. **"Every confirmed failure becomes a test that doesn't flake."**
   - A flagged turn becomes a regression case, with its tool responses **recorded and replayed**, gated in CI.
   - No live tools, so no side effects and no flakiness.

   Braintrust and LangSmith can rerun prompts, but none of the products found records and replays multi-turn
   tool responses as a first-class CI primitive. pytest-agentreplay shows the idea exists and is unclaimed.

If real-log validation (master document §15, E1–E3) shows teams don't care about (1), the positioning has
to change. (2) and (3) are not defensible on their own.

## 4. What competitors will easily copy

- Deterministic tool-ledger checks: any platform can add them as a scorer type. **Expect this within 6–12
  months of us proving they work.**
- The incident → prompt fix → re-eval loop: Braintrust Loop, Galileo Insights, Patronus Percival and Arize
  Alyx already exist.
- A CI gate: Promptfoo, DeepEval and Braintrust all have one.

**What is harder to copy (the moat candidates):**

- **Contract mining quality.** Turning raw traces into an accurate contract in minutes needs a corpus of
  real agent traces and labelled failures, which we don't have yet. That corpus is the long-term asset.
- **Being the neutral verifier.** Platform vendors grade agents built on their own platform, and model
  vendors grade their own models. A neutral, auditable, local-first verifier is a credible position for
  regulated buyers, *if* we stay neutral: no hosted Phoenix, no model-vendor coupling.
- **Vertical check packs.** Fintech refunds, airline changes, insurance claims: domain policies encoded as
  tested contracts. Slow to build and valuable.

## 5. Implications (feed the master document)

1. Drop the "Sentry for…" framing (Raindrop and Sentry own it).
2. Don't compete on tracing, dashboards or general evals.
3. Compete on **verdict precision with evidence**, **zero-setup local runs**, and **flake-free regression from
   production failures**.
4. Price against value for regulated, transactional agents, not against $39 seats.
5. Stay vendor-neutral: the consolidations (ClickHouse, OpenAI, Snyk) are exactly why a neutral verifier
   has room.
