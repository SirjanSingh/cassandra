# Session Log: 2026-09-10 — NLI layer (Layer 2), Hindi faithfulness, repo declutter

Branch: `feature/nli-and-hindi` (from `demo/mock-bot-integration`, the most complete branch —
carries all v2 + jury + PR + the mock-bot demo).

## Scope

Three things, all toward turning the deterministic checker into a defensible, market-unique
product (data-sovereign + multilingual):

1. **NLI layer** — the missing middle of the faithfulness cascade (rule → **NLI** → LLM), so
   free-text RAG evidence is verified by entailment instead of dropping to the LLM.
2. **Hindi faithfulness** — prove the deterministic rule is language-agnostic for structured
   facts (a ₹ amount is a fact in any language), via a Hindi agent in the demo.
3. **Declutter** — archive hackathon-era docs; clean, definitive `docs/`.

## Why (decisions)

- The deterministic rule only reads the structured tool ledger; it's blind to prose. Research
  (INFUSE/CLATTER/decomposed-entailment) shows the winning pattern is a **cascade**: cheap
  rule → NLI classifier → LLM only on borderline. We had layers 1 and 3; this adds layer 2.
- **No knowledge is hardcoded** — the NLI model judges only the (claim, evidence) pair; the
  evidence is the agent's own retrieved passage. This is the honest design (nli.py docstring).
- Multilingual is *mostly free*: the rule matches facts (₹/dates), which are language-neutral,
  so Hindi structured hallucinations are caught with **no model**. Free-text Hindi uses a
  multilingual NLI checkpoint via the same Layer 2 — no code change.
- Commercial thesis: on-prem + deterministic + multilingual = **data-sovereign** faithfulness
  (DPDP/RBI: data can't leave India; US SaaS + LLM-judge tools send it out). See
  `docs/NLI_AND_MULTILINGUAL.md` + `docs/PRODUCTION_ADOPTION.md`.

## Changes

- **New** `cassandra/nli.py` — `Verifier` protocol; `HeuristicNLI` (offline lexical stub,
  honest about being approximate); `TransformersNLI` (real cross-encoder, lazy, only when
  `NLI_MODEL` set + `sentence-transformers` installed); `get_verifier()` factory + cache;
  `check_claim()`. Multilingual by delegation (point `NLI_MODEL` at an mDeBERTa/XNLI model).
- `cassandra/oracle.py` — `score_case(..., evidence=None)` now runs rule → NLI → LLM;
  new `nli_verdict()` (Layer 2). Default `evidence=None` ⇒ every existing caller unchanged.
- `cassandra/config.py` + `.env.example` — `nli_model` setting.
- `demo/mock-bot-integration.html` — new **भारत बैंक (Hindi) agent** + `🇮🇳 Hindi` toggle;
  `₹`/`Rs.` added to the money extractor (a format, not a fact); Hindi honest-decline phrases.
- **New** `docs/NLI_AND_MULTILINGUAL.md` (plain-language design), `tests/test_nli.py` (9 tests).
- **Declutter**: 12 hackathon docs → `docs/archive/` (+ archive README). Active `docs/` now:
  ARCHITECTURE, CODEBASE_MAP, DEPLOYMENT, JURY_AND_PR, NLI_AND_MULTILINGUAL, PRD, PRODUCTION_ADOPTION,
  REQUIREMENTS, SYSTEM_DESIGN, TESTING_GUIDE, WORKFLOWS, blog, sessions/.
- README — added the cascade + multilingual subsection and the three checker modules to the tree.

## Verification

- `pytest` → **101 passed** (was 92; +9 in `tests/test_nli.py`). `ruff` clean on changed files.
- NLI heuristic verified on entailment/contradiction/neutral; oracle routing verified with a
  mocked verifier (LLM patched to explode → proves the NLI layer decides without the LLM).
- Hindi demo scenarios verified out-of-band (6/6 verdicts correct: hallucination on a
  fabricated ₹ fee, honest_decline on a Hindi decline, ok on grounded ₹ amounts).

## Open items

- NLI currently verifies the whole answer vs the passage; **atomic-claim decomposition** is the
  next refinement. A RAG adapter must pass the retrieved `evidence` for Layer 2 to fire.
- Wire `evidence` through the live pipeline (evaluator/replay) for real RAG agents (today it's
  plumbed in `oracle.score_case` but callers pass tool_calls only).
- Run a real `NLI_MODEL` end-to-end (needs `sentence-transformers` + a checkpoint) to replace
  the heuristic in a demo.
- Branch hygiene: `main`, `cassandra-v2`, `multi-agent-v1`, `demo/*` have diverged — consider
  consolidating once this lands (advisory; not done here).
