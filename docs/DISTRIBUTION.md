# Cassandra Distribution & Monetization Plan (post-hackathon)

Researched 2026-06-11 (deadline day). This captures where Cassandra can live beyond the
hackathon submission, what each channel costs to enter, and the recommended order.
Status of each item is tracked at the bottom.

## 1. VS Code — mostly zero-code (DONE for the zero-code tier)

Key finding: **VS Code natively supports MCP servers in Copilot agent mode**, and
competitors (Braintrust) already do IDE-native observability exactly this way — an MCP
server that Cursor, Claude Code, and VS Code query directly. `cassandra-mcp` already IS
that, so no extension is required for the core experience.

- **Zero-code tier (shipped 2026-06-11):** one-click "Install in VS Code" badge in the
  README (a `vscode.dev/redirect/mcp/install` deep link that prompts for the OpenAI key)
  plus a `.vscode/mcp.json` shipped in the repo so cloning auto-registers the server.
- **Real extension (later, only if traction):** value over plain MCP would be UI —
  CodeLens "Gate this prompt" buttons above system-prompt strings, an Incidents
  tree-view fed by the SSE feed, inline prompt-diff rendering. Path: VS Code's
  Language Model Tool API / AI extensibility APIs.

### The `onboard_agent` auto-discovery tool (first post-hackathon feature)

Build the "auto-pull agent details" idea **as an MCP tool, not an extension**: scan the
workspace for system prompts (string heuristics + known SDK call patterns like
`system_instruction=`, `messages=[{"role": "system"...`), detect whether
OpenInference/OTLP instrumentation exists, then generate the `.env`,
`BASELINE_PROMPT_FILE`, and a filled-in `examples/adapter_template.py`. As an MCP tool it
works in VS Code, Cursor, Claude Code, and Claude Desktop simultaneously; an extension
only works in one editor. Deliberately skipped on deadline day: invisible to judges in
the video/demo and risky new heuristic code.

## 2. GitHub Actions Marketplace — strongest near-term channel

Promptfoo validates the exact play (`promptfoo-action`: evaluates prompts on PR, posts a
pass/fail comment; a major discovery channel for them). Cassandra already has
`cassandra-gate` + `examples/github-actions-prompt-gate.yml`; packaging it as a published
Marketplace Action (`cassandra-gate-action`) is ~a day: composite action, PR comment with
the pass/fail table and prompt diff. Listing is free and searchable.

**Differentiator vs promptfoo** (declarative-config, offline): Cassandra gates against
the *live agent endpoint*, and eval datasets are **auto-synthesized from real production
failures** — the flywheel where every incident makes CI stricter.

## 3. Chrome extension — rejected

Bad fit: Cassandra supervises server-side traces; the browser has nothing to attach to.
The existing space is browser-automation agents (nanobrowser) or gimmicky "X-ray this
ChatGPT response" graders, and browser debugging itself is going MCP-shaped
(Chrome DevTools MCP). Energy is better spent where agent builders already are.

## 4. Free distribution channels (week-one checklist)

- **PyPI** — `pip install` is table stakes; pick a unique name (`cassandra` is taken by
  the database driver; consider `cassandra-supervisor`).
- **MCP registries** — 10,000+ MCP servers indexed by early 2026; list `cassandra-mcp`
  on the official MCP registry, Smithery, PulseMCP, mcp.so. Free.
- **The Arize relationship** — deepest Phoenix-MCP integration in their hackathon track;
  ask Arize to feature it in their community/integrations page regardless of result.
- **Show HN / r/LocalLLaMA launch** with the postmortem-flywheel story.

## 5. Monetization models that work for this shape of project

- **Langfuse open-core**: MIT core, free self-host; revenue from managed cloud +
  enterprise features (SSO, audit logs).
- **Promptfoo**: MIT core; $50/mo team cloud for collaboration/shared results.
- **MCP per-call billing** (Nevermined, Radius HTTP-402) exists but is immature —
  fewer than 5% of MCP servers are monetized.

Natural paid product for Cassandra: **"Cassandra Cloud" — a hosted supervision loop.**
User points it at their Phoenix/OTLP endpoint, gets continuous incidents-as-postmortems,
verified patches, and the auto-growing CI suite without running anything. Free tier =
N incidents/month; paid = continuous + **multi-agent supervision** (the planned registry
turning `patient_endpoint`/`patient_project`/`patient_prompt_name` into per-target
config becomes the paid feature). Market backdrop: LLM observability ~$2.7B in 2026,
growing ~36%/yr.

## Recommended sequence

1. ~~Submit the hackathon~~ (today, 2026-06-11 — nothing else matters until then).
2. **Week 1:** PyPI + MCP registries + GitHub Action on the Marketplace
   (+ ✅ VS Code one-click MCP install badge — shipped).
3. **Week 2–3:** the `onboard_agent` auto-discovery MCP tool (editor-agnostic).
4. **If traction:** VS Code extension with real UI; open-core hosted Cassandra Cloud.
5. **Never:** Chrome extension.

## Sources

- VS Code: [agent monitoring](https://code.visualstudio.com/docs/agents/guides/monitoring-agents) ·
  [Language Model Tool API](https://code.visualstudio.com/api/extension-guides/ai/tools) ·
  [AI extensibility overview](https://code.visualstudio.com/api/extension-guides/ai/ai-extensibility-overview)
- Competitive landscape: [Augment Code — agent observability tools](https://www.augmentcode.com/tools/best-ai-agent-observability-tools) ·
  [Confident AI — top LLM observability tools](https://www.confident-ai.com/knowledge-base/compare/top-7-llm-observability-tools) ·
  [MLflow — top agent observability tools](https://mlflow.org/top-5-agent-observability-tools/)
- GitHub Action pattern: [promptfoo-action](https://github.com/promptfoo/promptfoo-action) ·
  [promptfoo](https://github.com/promptfoo/promptfoo) ·
  [Promptfoo GitHub Action docs](https://www.promptfoo.dev/docs/integrations/github-action/)
- Business models: [Langfuse monetization handbook](https://langfuse.com/handbook/chapters/monetization) ·
  [Langfuse open-source strategy](https://langfuse.com/docs/open-source) ·
  [Promptfoo review/pricing](https://pecollective.com/tools/promptfoo/)
- MCP economy: [MCP adoption & monetization models](https://medium.com/mcp-server/the-rise-of-mcp-protocol-adoption-in-2026-and-emerging-monetization-models-cb03438e985c) ·
  [MCP monetization reality check](https://dev.to/krisying/mcp-servers-are-the-new-saas-how-im-monetizing-ai-tool-integrations-in-2026-2e9e) ·
  [Nevermined](https://nevermined.ai/blog/mcp-monetization-ai-agents) ·
  [Radius HTTP-402](https://www.radiustech.xyz/blog/mcp-server-monetization-with-radius)
- Chrome-extension rejection: [nanobrowser](https://github.com/nanobrowser/nanobrowser) ·
  [Chrome DevTools MCP](https://developer.chrome.com/blog/chrome-devtools-mcp) ·
  [AI response X-ray writeup](https://dev.to/aisarus/i-built-a-chrome-extension-that-x-rays-ai-responses-heres-what-i-learned-about-llm-quality-4e9k)
