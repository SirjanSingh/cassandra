# Cassandra — Winning Strategy

Why this project is built to place top-3 in the **Arize bucket**, and how every design
decision traces back to the judging criteria.

---

## 1. The Bucket Math

Six identical partner buckets, each paying 1st $5,000 / 2nd $3,000 / 3rd $2,000. You only
compete inside your chosen bucket.

> The Devpost page prose says "three identical prize buckets," but the official prize list
> enumerates all **six** partners (Arize, Elastic, Fivetran, GitLab, MongoDB, Dynatrace)
> each with 1st/2nd/3rd, and 6 × ($5k+$3k+$2k) = $60k = the stated total. The "three" is a
> stale typo; treat it as **six independent buckets**. (If clarified otherwise on the
> Discussions board, revisit — but the prize math is unambiguous.)

- MongoDB / Elastic — most crowded (everyone reflexively reaches for "vector DB").
- GitLab — crowded with developers.
- **Arize / Dynatrace — thinnest fields.** Most builders don't know what to do with an
  observability MCP server.
- Fivetran — under-picked but less photogenic.

**Decision: Arize.** Thinnest competitive field *and* the only bucket where the project's
core concept (an agent that does Phoenix's own workflow autonomously) is a perfect,
non-coincidental fit. We are not contorting an idea to fit a partner; the partner *is* the
idea.

## 2. Know Your Judges (confirmed from the official Devpost page)

The Arize-track panel is **Richard Young — Director of Partner Solutions, Arize** and
**Clay Miner — Head of Solutions Strategy, Arize**, alongside **Google Cloud Partner
Engineers** (Khushan Adatiya/SWE, Rich Deken, Jess Ambriz, Jon Pawlowski, Saurabh Kumar,
George Keller, Merlin Yamssi). Implications:

- These are **Solutions / Partner-Strategy leaders, not pure DevRel.** They reward
  demonstrated **business impact and credible solution architecture**, not just a slick
  product demo. The "engineer you don't have to hire" / cost-of-manual-triage framing in
  the demo script is aimed squarely at this audience — keep it.
- They will still expect **deep, correct, non-trivial Phoenix usage** over a token MCP
  ping, and will instantly recognize the manual Phoenix workflow Cassandra automates.
- The Google Partner Engineers score the **Google Cloud side**: clean Agent Builder /
  Gemini 3 implementation and a genuine MCP integration. Don't let the Phoenix story
  starve the Google-Cloud-quality signal.
- Generic multi-agent orchestration impresses no one here (table stakes).
- They watch the video muted first, then maybe with sound. They never run the code.

Cassandra is engineered for exactly this audience: it is the Phoenix product loop, made
autonomous, shown working on real traces.

## 3. Judging Criteria Map (each ~25%)

### Quality of the Idea — 25%

- A recursive, memorable thesis: **an agent whose job is supervising other agents.**
- Nearly every one of ~6,200 entries will *be* an agent. Almost none will be an agent
  *about* agents. Differentiation is structural, not cosmetic.
- Reinforced by the self-observability flourish (Cassandra is itself traced in Phoenix).
- Avoids every "overdone" category (no RAG chatbot, no support bot, no travel planner, no
  World Cup stats bot).

### Technological Implementation — 25%

- Exercises ≥5 Phoenix MCP tool families end-to-end: spans, annotations, datasets,
  experiments, prompt management (REQUIREMENTS §4, AC-6). Breadth + depth is precisely
  what partner-engineer judges score.
- Mandatory stack used genuinely: Gemini 3 reasoning over span trees, ADK LoopAgent
  pipeline, Vertex AI Agent Engine runtime, real MCP (not SDK shortcut).
- All Phoenix access isolated behind one wrapper — clean, reviewable software, not glue.

### Potential Impact — 25%

- Universal pain: *every* team running LLMs in production catches agent failures with
  human eyeballs today. The total addressable problem is "all production LLM systems."
- The fix is concrete and economically legible: replace manual trace-sampling and
  hand-authored evals with a continuous autonomous loop. The demo literally frames it as
  "the on-call engineer you don't have to hire."

### Design — 25%

- The dashboard is engineered as a *demo instrument*: a live, append-only feed where one
  customer message visibly cascades into annotation → dataset → experiment → patch diff
  within the 10-second latency budget (NFR-1, FR-DB5).
- Deep links into the real Phoenix UI prove the work is real, not mocked.
- The video script front-loads a striking, hard-to-fake wow in the first 30 seconds.

## 4. Strategic Principles (baked into the build)

1. **Partner integration is the product, not a checkbox.** Cassandra cannot exist without
   Phoenix; the MCP surface coverage is maximized on purpose.
2. **Vertical/operational beats horizontal/generic.** Last year's winners were vertical
   or attacked a specific operational pain. Cassandra attacks one sharp pain: silent
   agent failure in production.
3. **Orchestration is table stakes — do not pitch it as novelty.** We use LoopAgent
   because it fits, and we spend zero demo seconds bragging about it.
4. **The video is the deliverable.** Latency budget, deterministic seeder, fallback clip,
   and contrast-tuned numbers all exist to make 180 seconds undeniable.
5. **De-risk the unknown first.** The Phoenix MCP enumeration spike is Day 1; the
   annotation write-back is a hard Day-10 checkpoint above all other features.

## 5. What Would Lose

- Token MCP usage (one `list` call) — judged shallow.
- A generic "monitoring chatbot" framing — loses the recursive-idea edge.
- A demo that explains architecture before showing the catch — loses the first-30s war.
- Missing submission mechanics — disqualification regardless of quality. The official
  rule is specific: the repo must be **public** and the open-source license must be
  **detectable and visible in the GitHub About section** (i.e. a standard-form LICENSE
  GitHub's licensee detector recognizes — our verbatim Apache-2.0 file qualifies). Also
  required: hosted project URL, ~3-min video, track selected, Devpost form. Hence LICENSE
  + public repo on Day 1 and a Day-24 checklist.

## 6. One-Sentence Pitch (for the Devpost form)

> *Cassandra is an autonomous meta-agent that watches your production agents through
> Arize Phoenix, catches hallucinations and tool failures in seconds, turns each failure
> into a reproducible eval dataset, proves a fix with a Phoenix experiment, and hands you
> an A/B-ready prompt patch — the human you don't have to hire to babysit your agents.*
