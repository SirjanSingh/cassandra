# Who watches the watchmen? Building a meta-agent that supervises other AI agents — with Phoenix

*This started as a Google Cloud Rapid Agent Hackathon project (the Arize track), and the Arize
team kindly asked us to write up what we built and how Phoenix fit in. So here's the honest
version — including the part where we found out our own AI judge was quietly lying to us, and the
part where we rebuilt half the stack at 2am the night before the deadline.*

---

## First, who "we" are

We're a two-person team — **Kshitij** and **Sirjan**. [One or two honest lines each about who you
are: e.g. "Kshitij is a [student/engineer] who likes [X]; Sirjan is a [role] who's been deep in
[Y]." Keep it real and short.]

We ended up teaming up [how you two met — a class, a Discord, a mutual friend, a previous
project — one or two sentences]. What made it click was that we argued well: [one of us] tends to
push for shipping fast and demoing, [the other] tends to push for "but is this actually correct?"
— and this particular project lives exactly in the tension between those two instincts. More on
that in a bit, because it turned out to be the whole point.

## The problem: agents don't crash, they fib

Everyone building with LLM agents has felt this specific flavor of dread. Your agent doesn't
throw a stack trace. It doesn't 500. It just... makes something up, with total confidence, in a
perfectly friendly tone, and ships it straight to a customer.

Our demo villain for this is a little e-commerce support bot we called **ShopBot**. Ask it about
a refund policy for a region it doesn't have data for, and here's what happens under the hood:

- The tool `get_refund_policy("DE")` returns `{ "found": false }`.
- ShopBot, being a helpful people-pleaser, thinks: *I can't leave the customer hanging.*
- ShopBot replies: **"In Germany, you can return items within 14 days for a full refund!"**

That number is completely invented. There's no stack trace, no error, nothing red anywhere. The
only evidence that something went wrong is sitting in the **trace** — the tool said "I've got
nothing," and the model answered as if it had everything.

That gap — between what the tools actually returned and what the model confidently claimed — is
the entire ballgame. And it's invisible unless you're looking at your telemetry.

## The idea: an agent whose only job is to watch other agents

Today, catching this is a human job. Someone samples conversations by hand, writes eval cases by
hand, and edits prompts on intuition. It doesn't scale, and most failures are never caught at all.

So we built **Cassandra** — a meta-agent whose entire purpose is to supervise *other* agents. The
design rule we're proudest of: **Cassandra never touches the supervised agent's code.** It watches
purely through observability. It reads the agent's traces out of Phoenix, and everything it learns,
it learns from telemetry — exactly like an SRE watching a service through its dashboards, not by
SSH-ing into the box.

That decoupling is what makes it a *product* and not a demo. ShopBot is just the crash-test dummy.
Point Cassandra at any agent that exports traces to Phoenix and it works the same way.

## How it works: one failure in, one verified fix out

Cassandra runs an 8-stage loop. One incident goes in one end; a proven, evidence-backed prompt fix
comes out the other. Here's the whole thing, narrated with the German refund failure:

1. **Watch** — poll fresh traces from the Phoenix project (`patient-prod`), grab a new failing turn.
2. **Diagnose** — classify it: *hallucination / tool-failure / prompt-drift / ok*. (More on this
   step in a second, because it's where things got interesting.)
3. **Root-cause** — "the tool returned `found: false`; the prompt told the model to never admit
   ignorance; so it fabricated." The causal chain, not just the label.
4. **Synthesize** — turn that one failure into a whole adversarial eval dataset, written back into
   Phoenix.
5. **Evaluate (baseline)** — score the *current* prompt against those cases, live, on the real agent.
6. **Patch** — rewrite the system prompt to close the hole, registered as a new Phoenix prompt
   version with a unified diff.
7. **Replay** — re-run the *exact original failing question* on the patched prompt. Did this
   specific case actually get fixed?
8. **Red-team** — fire all the adversarial probes at both prompts and report the survival rate.

On our last run, that loop took ShopBot from **0% → 100%** on the synthesized suite, flipped the
replay from *"14-day German policy!"* to *"that policy is currently unavailable, let me connect you
to support,"* and 6/6 red-team probes survived the patch. Every artifact — the annotation, the
dataset, the prompt version — landed back in Phoenix, where a human on the team can review it.

## The honest twist: our judge was lying to us

Here's the part we promised to be honest about — and it's where our two instincts collided
productively.

Stage 2 (Diagnose) originally worked the way everyone's does: an **LLM-as-a-judge**. Ask a model
"did this other model mess up?" and trust its answer. It demoed beautifully. We even had a shiny
"100% diagnostic accuracy" number and were ready to show it off.

Then came the question that haunts this entire category: **"How do you know the judge is right?"**
(This is exactly the "but is it actually correct?" instinct earning its keep.)

So we actually dug into our own traces in Phoenix — and found something embarrassing. In our *test*
harness, the judge was being handed the tool results. But in the *production* path, a plumbing bug
meant the tool ledger never reached the judge. Our judge was grading hallucinations **without ever
seeing what the tools returned.** The impressive accuracy number was measuring the wrong code path.
Our judge sounded confident and was quietly unreliable — which, if you're keeping score, is *the
exact thing Cassandra exists to catch.* The supervisor had the disease.

The fix reframed the whole project. For a tool-using agent, **the tool ledger is ground truth.**
`get_refund_policy("DE") → {found: false}` is a *fact*, not an opinion. So instead of asking an LLM
"does this look like a hallucination?", we wrote a **deterministic grounding verifier**: for every
specific claim in the answer, is there a successful tool call that backs it?

- Claim with no supporting successful tool call → **hallucination** (and here's the exact call that
  proves it).
- A field the tool returned as `null` but the answer stated anyway → **tool-failure**.
- Claim backed by a real, successful result → **ok**.
- Can't tell from the rules? → **abstain**, and *only then* fall back to the LLM.

Now the load-bearing verdict isn't a vibe from a language model — it's a reproducible check over
structured telemetry that can cite its evidence. The LLM went from being the judge to being the
fallback. That single change is the difference between "we wrap an API" and "we have a moat."

## The 2am part: the deadline scramble

No honest hackathon writeup is complete without the last-night chaos, so here it is.

The night before the deadline, we re-read the rules properly and realized our hosted demo was
running on the wrong model provider — and the hackathon required Gemini. That's a
disqualification-level problem, discovered with hours to spare. So we did the responsible,
terrifying thing: **migrated the entire hosted stack to Vertex AI Gemini in one sitting.**

That, of course, uncovered a chain of bugs that only ever appeared on the Gemini path:

- **"Cannot send a request, the client has been closed."** A subtle one — the genai client was
  getting garbage-collected mid-request because we weren't holding a reference across the `await`.
  The whole supervision loop was silently no-op-ing. One-line fix, hours to find.
- **Quota exhaustion.** Our first model choice kept returning `429 RESOURCE_EXHAUSTED` under any
  burst (shared quota, no knob to turn). We swapped to a lighter Gemini variant with a roomier pool.
- **Evaluator timeouts.** The eval stage fired every probe at the live agent at once, which
  bottlenecked on quota and blew the HTTP timeout. We bounded it with a semaphore.

This is the part where a two-person team actually matters: one of us drove the deploy and watched
the container logs while the other chased the client-lifecycle bug in the code, and we just
ping-ponged fixes until the full pipeline ran green end-to-end on Gemini. We shipped it running on
a Google Compute Engine VM behind a tunnel, watched one clean autonomous cycle complete, and
*then* went to sleep. Winning the track a bit later made the sleep deprivation retroactively worth
it.

## Where Phoenix actually earned its keep

We want to be specific here, because Phoenix wasn't a checkbox — it's load-bearing in about four
different ways:

- **Traces + tool spans (`patient-prod`).** This is the raw material. The whole deterministic
  verifier is only possible because the tool calls and their results are captured as spans. No
  telemetry, no ground truth, no product. The OpenInference spans gave us exactly the
  input/output/tool structure we needed.
- **Annotations.** When Cassandra confidently diagnoses a failure, it writes an annotation back
  onto the offending span — so the diagnosis lives *on the trace*, where a human reviewing in
  Phoenix sees it in context.
- **Datasets.** Every synthesized adversarial suite becomes a Phoenix dataset. Over time that's a
  growing, versioned regression corpus minted from your *own* incidents — the thing you can't get
  anywhere else.
- **Prompt versions.** Candidate fixes are registered as Phoenix prompt versions (never
  auto-promoted — a human approves). The diff, the metadata, the failure class it addresses — all
  right there.
- **The MCP gateway (`@arizeai/phoenix-mcp`).** Cassandra talks to Phoenix entirely through the MCP
  server, behind a single gateway module. That kept the integration clean and, honestly, made the
  whole thing feel like plugging into an actual platform rather than scraping an API.

## The recursive bit we can't resist mentioning

Because Cassandra's whole pitch is "your agent should be observable and measurable," it felt
dishonest not to hold *itself* to that. So Cassandra traces its **own** reasoning into a second
Phoenix project (`cassandra-meta`), and it runs a self-evaluation: a hand-labeled library of trick
cases fed through its own diagnostician, scored against ground truth.

The watcher, watching itself, in Phoenix. That was the moment the project clicked for both of us —
the supervisor is exactly as observable as the agents it supervises, because it's using the same
telemetry stack to keep itself honest. (Current self-score: 10/11. It's not perfect. Neither are
we. That's kind of the point.)

## What we'd tell you if you're building agents

Three things we actually believe now that we didn't before:

1. **Your traces are not just for debugging — they're ground truth for evaluation.** The tool
   ledger can decide most failure classes deterministically. Use it.
2. **Stop fully trusting an LLM to grade an LLM.** Make it prove its verdict against telemetry, and
   keep the language model for the genuinely fuzzy cases.
3. **Close the loop.** Detecting a failure is table stakes. The value is turning it into a
   regression test, proving a fix, and blocking it from coming back.

Cassandra was a hackathon project, but building it changed how we think about agent reliability —
and a shocking amount of that came from just *reading our own traces honestly.* Turns out the
uncomfortable answers were sitting in Phoenix the whole time.

Thanks to the Arize team for the nudge to write this up — and for building the observability layer
that a project like this literally couldn't exist without. 🙏

*— Kshitij & Sirjan. Cassandra is open-source (Apache-2.0) at [repo link].*
