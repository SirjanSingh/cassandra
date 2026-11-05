"""Run Cassandra's real fix stages on one TravelPal incident.

Diagnostician.judge -> RootCauseAnalyst.analyze -> Patcher.propose, exactly as the
pipeline calls them. Only the Phoenix gateway is stubbed (Phoenix isn't required for
this PoC): the prompt version the Patcher would upsert is written to
candidate_prompt.txt instead.

    python -m poc.travelpal.fix_loop [--incident q090]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from cassandra.diagnostician import Diagnostician
from cassandra.models import Incident, SpanRecord
from cassandra.patcher import Patcher
from cassandra.rootcause import RootCauseAnalyst
from poc.travelpal.agent import SYSTEM_PROMPT

HERE = Path(__file__).parent


class _LocalPhoenix:
    """Stands in for PhoenixMCP: records the prompt version instead of upserting it."""

    def __init__(self) -> None:
        self.versions: list[dict] = []

    @asynccontextmanager
    async def session(self):
        yield self

    async def create_prompt_version(self, name: str, prompt_text: str, metadata: dict) -> str:
        self.versions.append({"name": name, "metadata": metadata})
        return f"local-{len(self.versions)}"

    def span_url(self, span: SpanRecord) -> str:
        return ""


async def main(incident_id: str) -> None:
    runs = {json.loads(line)["id"]: json.loads(line)
            for line in (HERE / "runs.jsonl").read_text(encoding="utf-8").splitlines()}
    r = runs[incident_id]
    span = SpanRecord(
        span_id=incident_id, trace_id=incident_id, project="travelpal-prod",
        started_at=datetime.now(timezone.utc), input_text=r["question"],
        output_text=r["reply"], session_id="prod", tool_calls=r["tool_calls"],
    )
    phx = _LocalPhoenix()
    inc = Incident.from_span(span)
    inc.baseline_prompt = SYSTEM_PROMPT  # what BASELINE_PROMPT_FILE would supply

    inc.verdict = await Diagnostician(mcp=phx).judge(span.input_text, span.output_text, span.tool_calls)  # type: ignore[arg-type]
    print(f"verdict: {inc.verdict.failure_class.value} ({inc.verdict.confidence}) {inc.verdict.rationale}")
    inc = await RootCauseAnalyst(mcp=phx).analyze(inc)  # type: ignore[arg-type]
    print(f"root cause: {inc.root_cause.summary}\nfix strategy: {inc.root_cause.fix_strategy}")
    inc = await Patcher(mcp=phx).propose(inc)  # type: ignore[arg-type]

    (HERE / "candidate_prompt.txt").write_text(inc.candidate_prompt or "", encoding="utf-8")
    (HERE / "fix_loop.json").write_text(json.dumps({
        "incident": incident_id, "question": r["question"], "bad_answer": r["reply"],
        "verdict": inc.verdict.model_dump(mode="json"),
        "root_cause": inc.root_cause.model_dump(mode="json"),
        "prompt_diff": inc.prompt_diff, "prompt_versions": phx.versions,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n--- prompt diff ---\n" + (inc.prompt_diff or ""))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--incident", default="q090")
    asyncio.run(main(ap.parse_args().incident))
