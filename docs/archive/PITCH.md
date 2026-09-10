# Cassandra: The Meta-Agent That Watches Other Agents

*Pitch for the Google Cloud Rapid Agent Hackathon, Arize track. This is the narrative for the website, the Devpost page, and the demo video.*

## The one-liner

Every production LLM agent fails silently. Cassandra is an agent whose only job is to catch those failures, prove a fix, and attack its own fix, all without a human in the loop.

## The problem

Teams running LLM agents in production share one unsolved problem: agents fail quietly and confidently. A support bot invents a refund policy that does not exist. A tool call returns nothing and the agent papers over the gap with a fabricated delivery date. A model upgrade drifts the prompt's behavior overnight.

Today this is caught by humans staring at trace dashboards, sampling conversations by hand, writing eval datasets manually, and editing prompts on intuition. It is slow, it does not scale, and most failures are never caught at all.

## The idea

Cassandra closes that loop autonomously. It is, recursively, an agent that supervises other agents. It connects to Arize Phoenix, the observability platform the supervised agent already exports traces to, and runs the exact workflow Phoenix was built for, but automated, continuous, and self-improving:

1. **Watch.** Poll fresh production traces from Phoenix.
2. **Diagnose.** An LLM-as-judge classifies each failure: hallucination, prompt drift, or tool failure, with a confidence and severity.
3. **Root-cause.** Pinpoint the culprit and a causal chain: which tool returned nothing, which prompt line told the model to fabricate.
4. **Synthesize.** Turn that single failure into an adversarial eval dataset, written back into Phoenix.
5. **Evaluate.** Score the current prompt against the dataset, live, on the real agent.
6. **Patch.** Rewrite the system prompt to close the failure, registered as a Phoenix prompt version with a unified diff.
7. **Replay.** Re-run the exact original failing input on the patched prompt and judge whether this specific case is now fixed.
8. **Red-team.** Fire the adversarial probes at the live agent, current prompt versus patched prompt, and show the survival rate.

One incident in, one verified, evidence-backed prompt patch out. Every artifact (annotation, dataset, experiment scores, prompt version) lands in Phoenix where the team already works.

## The recursive twist

Cassandra also watches itself. Its own reasoning is traced into a second Phoenix project, and a built-in self-evaluation runs a hand-labeled trap library through its own Diagnostician and scores its diagnostic accuracy against ground truth. The supervisor is as observable and as measurable as the agents it supervises.

## What you see in the demo

A live cockpit. You type a customer message; the victim agent ("the Patient", a deliberately fragile ShopBot) confidently invents a refund policy. Seconds later Cassandra catches it in the trace feed and the full pipeline plays out on screen: the diagnosis, the causal chain, the synthesized attack set, baseline versus candidate pass rates, the prompt diff, the before-and-after replay, and the red-team table. Then you press "Grade my own diagnoses" and Cassandra scores itself.

## Why it wins the Arize track

- **Quality of the idea.** Almost every entry will be an agent. Almost none will be an agent about agents. The concept is memorable, recursive, and obviously useful.
- **Technical implementation.** It exercises nearly the entire Phoenix MCP surface (traces, spans, annotations, datasets, prompts) and publishes its own MCP server, `cassandra-mcp`, so any agent or IDE can call `diagnose`, `synthesize_evals`, `propose_patch`, `supervise_latest`, or `self_evaluate`.
- **Impact.** Every production LLM team has this exact pain and currently solves it with eyeballs.
- **Design.** The whole loop is visible live: a failure is caught, diagnosed, patched, and verified on camera in under a minute.

## Built with

Gemini on Vertex AI (with OpenAI and OpenRouter fallbacks), Google ADK LoopAgent on Vertex AI Agent Engine, Arize Phoenix via the partner MCP server, FastAPI on Cloud Run, Firestore for durable state, Secret Manager for keys.

## The tagline

Agents fail silently. Cassandra hears them.
