# Mock-bot integration demo

A **standalone, visual** demo of how Cassandra plugs into a real tool-calling agent.
No install, no server, no keys — **open `mock-bot-integration.html` in any browser.**

## What it shows

A realistic **bank support assistant** ("Meridian Bank") on the left — the kind of
tool-calling agent you'd actually ship — and a live **Cassandra faithfulness monitor**
on the right.

Click a suggested question. The bot "thinks", calls a tool (e.g. `get_fee`,
`get_transaction`), and answers. On the right, Cassandra shows, for that same answer:

- **the tool ledger** (the receipts — what each tool returned, `found:true/false`),
- **the claim** it extracted from the answer (a fee, a date, a status),
- **the verdict** — GROUNDED / UNGROUNDED — with the **failure class** and the **exact tool
  call cited as proof**,
- running **metrics** (answers checked, ungrounded count, ungrounded rate).

### The toggle: Fragile vs Hardened prompt

- **Fragile prompt** — when a tool returns nothing, the bot *fabricates* (invents a fee, a
  delivery date, a "completed" status). Watch the ungrounded rate climb.
- **Hardened prompt** — the same bot now *declines honestly* ("I don't want to quote you the
  wrong number…"). Cassandra scores those as **GROUNDED — honest decline**.

That contrast is the whole product thesis in one click: *you can tell a bot to say "I'm not
sure," but only a check against the receipts proves it actually did.*

## How this maps to the real system

The demo is self-contained (the bot is scripted so it always works and always hallucinates
on cue), but the **integration pattern is the real one**:

| In the demo | In production (`cassandra/`) |
|---|---|
| Scripted bot + tool results | Your real agent emitting OpenInference **traces** to Phoenix |
| The JS `checkGrounding()` | `cassandra/grounding.py` + `oracle.py` (the deterministic checker) |
| The right-hand verdict cards | Phoenix **annotations** + the postmortem |
| The ungrounded-rate metric | The KPI you'd alert & gate on |
| Fragile → Hardened toggle | The Patcher's proposed fix (a human approves) |

The checker logic here is a faithful JS port of the Python grounding rules: for every claim
the bot makes, *is there a successful tool result that backs it?* — no second LLM, a
reproducible rule that cites its evidence.

## Note

This is a **demo/branch artifact** (`demo/mock-bot-integration`), not part of the shipped
package. It exists to make the integration visually obvious for pitches and onboarding.
