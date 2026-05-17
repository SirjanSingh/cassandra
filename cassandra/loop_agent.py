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
# SPIKE-RECONCILE: confirm google-adk APIs (LoopAgent / SequentialAgent / tool
# adaptation) for the pinned SDK version, then map each stage to an ADK sub-agent.
# The pipeline above is the source of truth; ADK is the runtime envelope so the
# project satisfies the "built with Agent Builder / Agent Engine" requirement.

def build_adk_agent():  # pragma: no cover - runtime wiring, validated on deploy
    from google.adk.agents import LoopAgent, SequentialAgent  # type: ignore

    pipeline = SupervisionPipeline()

    async def _tick(_ctx) -> dict:
        inc = await pipeline.run_once()
        return {"handled": inc.incident_id if inc else None}

    supervision = SequentialAgent(name="supervision_pipeline", sub_agents=[])
    return LoopAgent(
        name="cassandra",
        sub_agents=[supervision],
        # one incident per cycle; the scheduler (Cloud Function) drives cadence
        max_iterations=1,
        before_agent_callback=_tick,
    )
