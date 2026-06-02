"""The supervision pipeline + its ADK LoopAgent wiring (FR-L1..L3).

The pipeline LOGIC is plain, testable Python (`SupervisionPipeline`). ADK
(`LoopAgent` + `SequentialAgent`) is the orchestration shell required by the
hackathon stack - kept thin and isolated at the bottom so the logic can be unit
tested without a live ADK/Agent Engine runtime.
"""

from __future__ import annotations

from .diagnostician import Diagnostician
from .evaluator import Evaluator
from .models import Incident
from .patcher import Patcher
from .redteam import RedTeam
from .replay import TraceReplay
from .rootcause import RootCauseAnalyst
from .state import get_state
from .synthesizer import Synthesizer
from .watcher import Watcher
from patient.agent import FRAGILE_SYSTEM_PROMPT


class SupervisionPipeline:
    """Watcher -> Diagnostician -> Synthesizer -> Evaluator(base) -> Patcher ->
    Evaluator(candidate). One incident per cycle, deduped by span id."""

    def __init__(self) -> None:
        self.watcher = Watcher()
        self.diagnostician = Diagnostician()
        self.rootcause = RootCauseAnalyst()
        self.synthesizer = Synthesizer()
        self.evaluator = Evaluator()
        self.patcher = Patcher()
        self.replay = TraceReplay()
        self.redteam = RedTeam()
        self.state = get_state()

    async def run_once(self) -> Incident | None:
        """Process exactly one fresh failing incident, or return None (FR-L1)."""
        incidents = await self.watcher.poll()
        for inc in incidents:
            inc = await self.diagnostician.diagnose(inc)
            self.state.mark_seen(inc.span.span_id)  # FR-L3 dedupe regardless of verdict
            if inc.verdict is None or not inc.verdict.is_failure:
                continue

            inc = await self.rootcause.analyze(inc)          # why it broke
            inc = await self.synthesizer.synthesize(inc)      # eval generation
            inc = await self.evaluator.run_baseline(inc, FRAGILE_SYSTEM_PROMPT)
            inc = await self.patcher.propose(inc)             # prompt fixing
            inc = await self.evaluator.run_candidate(inc)
            inc = await self.replay.replay(inc)               # live trace replay
            inc = await self.redteam.attack(inc)              # adversarial testing
            return inc  # yield after one full cycle (demo-deterministic)
        return None


# --- ADK orchestration shell ---------------------------------------------------
# The pipeline above is the source of truth (plain, unit-tested Python). ADK is the
# runtime envelope so the project satisfies the "built with Agent Builder / ADK +
# Vertex AI Agent Engine" requirement. `SupervisionAgent` is a real ADK custom
# BaseAgent (validated against google-adk 2.1.0): it runs one supervision cycle per
# invocation and reports the handled incident through session state; `LoopAgent`
# drives the cadence on Agent Engine.


def build_adk_agent():
    from google.adk.agents import BaseAgent, LoopAgent
    from google.adk.agents.invocation_context import InvocationContext
    from google.adk.events import Event, EventActions

    class SupervisionAgent(BaseAgent):
        """ADK custom agent wrapping one Cassandra supervision cycle."""

        async def _run_async_impl(self, ctx: InvocationContext):
            inc = await SupervisionPipeline().run_once()
            handled = inc.incident_id if inc else None
            yield Event(
                author=self.name,
                actions=EventActions(
                    state_delta={
                        "cassandra.handled": handled,
                        "cassandra.stage": inc.stage.value if inc else None,
                        "cassandra.failure_class": (
                            inc.verdict.failure_class.value
                            if inc and inc.verdict
                            else None
                        ),
                    }
                ),
            )

    return LoopAgent(
        name="cassandra",
        description="Meta-agent: supervises production agents via Arize Phoenix.",
        sub_agents=[SupervisionAgent(name="supervision_cycle")],
        # one incident per cycle; the scheduler (Cloud Function) drives cadence.
        max_iterations=1,
    )
