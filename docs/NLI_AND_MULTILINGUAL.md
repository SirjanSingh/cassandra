# NLI layer + multilingual (Hindi) faithfulness

Plain-language design for the two additions on `feature/nli-and-hindi`.

---

## Why

The original checker (`cassandra/grounding.py`) is a **rule** that reads the **structured
tool ledger** (`{found:false}`). It's precise, free, and cites its evidence — but it's blind
to **prose**. When a RAG agent answers from a *retrieved paragraph*, there's no field to
compare, so the rule abstains and everything drops to the LLM judge (fuzzy, non-deterministic,
and it sends your data to a model).

Two upgrades close that gap.

## 1. The NLI layer — the missing middle of the cascade

**NLI = Natural Language Inference.** A small, pre-trained model that answers one narrow
question about two texts: does text A **entail** text B? (entailment / contradiction /
neutral). We use it to ask: *does the retrieved evidence support the agent's claim?*

```
answer + evidence
      │
  Layer 1  grounding rule   → structured tool result?      cheap · exact · cites receipt
      │  (can't decide: prose)
  Layer 2  NLI (nli.py) ★   → does the passage ENTAIL it?  cheap · no LLM · multilingual
      │  (still unsure)
  Layer 3  LLM judge        → last resort
```

**No knowledge is hardcoded.** The model judges only the *relationship* between the claim and
the agent's **own retrieved evidence** — we bake in zero facts about any domain. The data it
sees is whatever the agent retrieved, nothing of ours.

**Example (insurance RAG):**
| | text |
|---|---|
| claim (bot said) | "Water damage is fully covered." |
| evidence (retrieved) | "Sudden discharge is covered; gradual seepage is **excluded**." |
| NLI verdict | **contradiction** → UNGROUNDED |

The rule couldn't touch that; NLI catches it. This **extends coverage from tool-calling agents
to document-RAG agents.**

### Implementation
- `cassandra/nli.py` — a pluggable `Verifier` interface with two backends:
  - **`TransformersNLI`** (production) — a HuggingFace cross-encoder, loaded only when
    `NLI_MODEL` is set and `sentence-transformers` is installed. English default
    `cross-encoder/nli-deberta-v3-small`; set a multilingual checkpoint for Hindi.
  - **`HeuristicNLI`** (offline dev/test stub) — lexical overlap + generic negation cues.
    Deliberately simple and honest about being approximate; **not** the production path.
- `cassandra/oracle.py` — `score_case(..., evidence=None)` now runs the cascade
  rule → NLI → LLM. Default `evidence=None` means every existing caller is unchanged.
- `NLI_MODEL` in `.env.example` / `config.py`.

### Honest limitations
- The offline heuristic is weak; real entailment needs the model (`NLI_MODEL`).
- We currently verify the whole answer against the passage; **atomic-claim decomposition**
  (verify each claim separately) is the next refinement.
- NLI is only reached when free-text `evidence` is supplied — a RAG adapter must pass the
  retrieved passage alongside the answer.

## 2. Multilingual / Hindi — mostly free, by design

The deterministic rule is **already language-agnostic for structured facts**: a ₹ amount, a
date, or a policy number is the same fact whether the sentence is English or Hindi. So the
checker catches a Hindi hallucination **with no model at all** — the differentiator no
English-only tool has.

```
Hindi answer:  "…वायर ट्रांसफ़र का शुल्क ₹1,500 है।"   (fee is ₹1,500)
tool result:   get_fee(intl) → {found:false}            (no data)
rule:          ₹1,500 claim, no successful tool → HALLUCINATION ✓
```

- The demo (`demo/mock-bot-integration.html`) adds a **भारत बैंक (Hindi) agent** proving
  this end-to-end — the same checker, different language, zero extra model.
- Only two **formats** were added (not facts): a `₹`/`Rs.` money pattern, and a few Hindi
  honest-decline phrases so an honest "जानकारी उपलब्ध नहीं" scores GROUNDED.
- For **free-text** Hindi, Layer 2 handles it: point `NLI_MODEL` at a multilingual NLI
  checkpoint (e.g. `mDeBERTa-v3-base-xnli`) — same code path, no changes.

## Why this matters commercially
Structured, language-agnostic + on-prem NLI means faithfulness checking that **never sends
data to a foreign API** and **works in Indian languages** — exactly what DPDP/RBI-regulated
Indian fintech/health teams need and what US SaaS + English-LLM-judge tools can't offer. See
`docs/PRODUCTION_ADOPTION.md` and the product-research report.
