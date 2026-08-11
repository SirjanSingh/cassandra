# Cassandra — Market Sizing (TAM / SAM / SOM)

> Market research for Cassandra, the meta-agent that supervises other AI agents.
> Figures below are a mix of cited third-party market reports (TAM) and top-down
> reasoning (SAM / SOM). Treat SAM and SOM as **defensible estimates**, not audited
> numbers — anchor any external claim on the TAM sources in §5.
>
> _Last updated: 2026-08. Author: Cassandra team._

---

## 0. TL;DR

| Layer | Definition | Size (2026) | Basis |
|-------|-----------|-------------|-------|
| **TAM** | The whole LLM observability + evaluation market | **~$2.7B** (→ ~$9B by 2030, ~36% CAGR) | Cited market reports (§5) |
| **SAM** | Teams running tool-using, customer-facing AI agents who need eval + reliability | **~$0.8B–$1.2B** | Top-down slice of TAM (§3) |
| **SOM** | What we can realistically win in the first 1–3 years | **~$3M–$10M ARR** (~1–3% of SAM) | Wedge + design-partner model (§4) |

**One-liner:** the market we sit in is ~$2.7B and growing ~36%/year; our specific
target (agents that can't afford confident mistakes) is ~$1B; realistically we chase
low-single-digit millions of it first, via a free CI gate + open-source core.

---

## 1. What market are we in?

Cassandra sits in **LLM / AI-agent observability and evaluation** — but with a twist that
defines our wedge. The category today splits into two layers:

- **Layer A — Observe & Evaluate (crowded):** watch traces, run evals, manage prompts.
  Incumbents: Arize (Phoenix + AX), LangSmith, Braintrust, Langfuse, Galileo, Maxim,
  Helicone. This layer is well-funded and competitive.
- **Layer B — Autonomously *fix and verify* (nascent):** detect a failure, prove a fix,
  and stop it recurring. Today this exists mostly as research (self-healing agents,
  panel-of-judges papers) and as features incumbents *could* add — **not** as an
  established product.

**Cassandra's position:** the reliability / remediation layer that runs *on top of*
whatever observability a team already uses, with a **deterministic** verdict at its core
(not an LLM grading an LLM). That is the differentiator and the reason we're not "just
another dashboard."

---

## 2. TAM — Total Addressable Market

**~$2.7B in 2026, growing ~36% CAGR to ~$9B by 2030.**

The LLM Observability Platform market was valued around **$1.97B (2025)** and **~$2.69B
(2026)**, on a **~36% CAGR**, projected to reach **~$9.26B by 2030**. Gartner adds a strong
tailwind: by **2028, LLM observability will be part of ~50% of GenAI deployments** (up from
~15% in early 2026).

**Why the whole market is our TAM ceiling:** every team running LLMs in production is a
theoretical buyer of "make my AI reliable and observable." This is the umbrella all our
competitors compete under.

**Growth drivers:** enterprise GenAI adoption, agentic/tool-using systems, fear of
hallucinations and silent failures, AI governance/audit requirements, and cost control.

---

## 3. SAM — Serviceable Addressable Market

**~$0.8B–$1.2B (a focused slice of TAM).**

We narrow the TAM to buyers Cassandra is *specifically* built for:

- **Tool-using, customer-facing agents** where a confidently-wrong specific fact costs real
  money — the exact failure our deterministic checker catches.
- **Target verticals:** fintech, insurance, healthcare, regulated support, logistics /
  e-commerce.
- **Technical fit:** teams already emitting traces (OpenInference / OpenTelemetry /
  Phoenix / Langfuse) — so integration is "point us at your logs," not a rewrite.
- **Reachable by our product shape:** open-source core + hosted plane + CI gate + MCP server;
  cloud-native, English-first teams first.

**Sizing logic (top-down):** roughly **30–45%** of the LLM-observability spend is on the
evaluation / reliability side (vs. pure tracing/monitoring), and Cassandra's agent-reliability
wedge is a meaningful share of that. Applying ~35% to a ~$2.7B TAM lands SAM near **~$0.95B**,
with a **~$0.8B–$1.2B** band to account for estimate uncertainty. This grows with the market
(~36% CAGR), so SAM roughly doubles by ~2028.

---

## 4. SOM — Serviceable Obtainable Market

**~$3M–$10M ARR within the first 1–3 years (~1–3% of SAM).**

As an early, small team we don't win the SAM — we win a beachhead:

- **Wedge (low friction):** the free **CI prompt-regression gate** + **open-source core** +
  the **MCP server** that drops into VS Code / Cursor. This seeds usage bottom-up inside
  engineering teams.
- **Land:** 3–5 **design partners** running customer-facing agents who've been burned by a
  silent failure — free/cheap in exchange for logos, feedback, and case studies.
- **Expand:** from the free gate into the hosted platform (owned dataset store, dashboards,
  team features, RBAC/SSO) — the paid plane.
- **Realistic ceiling:** a few dozen paying teams at typical dev-infra pricing (seats +
  usage) → **~$3M–$10M ARR** is a credible 2–3 year target if the wedge converts. The rest of
  SAM opens up later with enterprise features and multi-model coverage.

**Pricing reference points (2026):** Langfuse free self-host → ~$29/mo; LangSmith $39/seat +
$0.50/1k traces; Braintrust free 1GB → $249/mo; Galileo free 5k traces → $100/mo. We meter on
the *verb that creates value* (agents supervised / regression suites maintained), not raw
spans — a differentiated pricing axis vs. the observability incumbents.

---

## 5. Sources

- market.us — LLM Observability Platform Market ($1.97B 2025 → $2.69B 2026, ~36% CAGR):
  <https://market.us/report/llm-observability-platform-market/>
- ResearchAndMarkets — LLM Observability Platform Market Report 2026:
  <https://www.researchandmarkets.com/reports/6215671/large-language-model-llm-observability>
- Gartner — LLM observability in ~50% of GenAI deployments by 2028:
  <https://www.gartner.com/en/newsroom/press-releases/2026-03-30-gartner-predicts-by-2028-explainable-ai-will-drive-llm-observability-investments-to-50-percent-for-secure-genai-deployment>
- Galileo — Best AI Agent Evaluation Platforms 2026 (competitive landscape + pricing):
  <https://galileo.ai/blog/best-ai-agent-evaluation-platforms>
- Latitude — Best AI Agent Observability Tools 2026:
  <https://latitude.so/blog/best-ai-agent-observability-tools-2026-comparison>
- Braintrust — Arize alternatives 2026:
  <https://www.braintrust.dev/articles/arize-ai-alternatives-2026>

---

## 6. Caveats

- **TAM** is from third-party reports and is the most defensible number here.
- **SAM / SOM** are top-down estimates built on stated assumptions (§3–§4); different
  analysts would land differently. Present them as reasoning, not fact.
- Market-report figures vary by firm (some cite $0.5B, some $3.2B for "LLM observability")
  because of differing scope definitions — we use the mid-range, agentic-inclusive numbers.
- Re-validate annually; this space is moving fast (Gartner's 15% → 50% jump is the headline).
