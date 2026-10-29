"""Drive every question through TravelPal over Cassandra's HTTP contract.

Writes poc/travelpal/runs.jsonl (question, reply, tool ledger). Uses
cassandra.patient_client.ask_patient — the exact call Cassandra's stages make.

    python -m poc.travelpal.collect [--endpoint http://127.0.0.1:8090/chat]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from cassandra.patient_client import ask_patient

HERE = Path(__file__).parent


async def main(endpoint: str, concurrency: int) -> None:
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=120) as client:
        async def one(q: dict) -> dict:
            async with sem:
                r = await ask_patient(client, q["question"], endpoint=endpoint)
                return {**q, "reply": r["reply"], "tool_calls": r.get("tool_calls", [])}

        rows = await asyncio.gather(*(one(q) for q in questions))

    out = HERE / "runs.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"wrote {len(rows)} runs -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:8090/chat")
    ap.add_argument("--concurrency", type=int, default=6)
    a = ap.parse_args()
    asyncio.run(main(a.endpoint, a.concurrency))
