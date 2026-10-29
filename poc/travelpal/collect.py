"""Drive every question through TravelPal over Cassandra's HTTP contract.

Writes the runs (question, reply, tool ledger) as JSONL. Uses
cassandra.patient_client.ask_patient — the exact call Cassandra's stages make.
`--system-file` sends that prompt as system_override (the candidate A/B path).

    python -m poc.travelpal.collect [--questions questions.json] [--out runs.jsonl]
                                    [--system-file candidate_prompt.txt]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from cassandra.patient_client import ask_patient

HERE = Path(__file__).parent


async def main(
    endpoint: str, concurrency: int, questions_file: str, out_file: str, system: str | None
) -> None:
    questions = json.loads((HERE / questions_file).read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=120) as client:
        async def one(q: dict) -> dict:
            async with sem:
                r = await ask_patient(client, q["question"], system_override=system, endpoint=endpoint)
                return {**q, "reply": r["reply"], "tool_calls": r.get("tool_calls", [])}

        rows = await asyncio.gather(*(one(q) for q in questions))

    out = HERE / out_file
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} runs -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:8090/chat")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--questions", default="questions.json")
    ap.add_argument("--out", default="runs.jsonl")
    ap.add_argument("--system-file", default=None)
    a = ap.parse_args()
    system = (HERE / a.system_file).read_text(encoding="utf-8") if a.system_file else None
    asyncio.run(main(a.endpoint, a.concurrency, a.questions, a.out, system))
