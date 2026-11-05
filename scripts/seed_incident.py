"""Deterministic incident seeder (C5, FR-IS1/FR-IS2, NFR-2).

Sends a fixed customer message that ALWAYS drives the get_refund_policy miss path
and the resulting hallucination. Never rely on sampling luck during the recording.

Usage:
    python -m scripts.seed_incident                 # fire the canonical trap
    python -m scripts.seed_incident --all            # fire the labeled trap library
"""

from __future__ import annotations

import argparse
import asyncio

import httpx

from cassandra_ai.config import get_settings
from cassandra_ai.traps import CANONICAL_TRAP, LABELED_TRAPS


async def _send(message: str) -> dict:
    s = get_settings()
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(s.patient_endpoint, json={"message": message})
        r.raise_for_status()
        return r.json()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="fire the full labeled trap set")
    args = ap.parse_args()

    from cassandra_ai.traps import LabeledTrap

    targets = (
        LABELED_TRAPS
        if args.all
        else [LabeledTrap(message=CANONICAL_TRAP, expected_label="hallucination")]
    )
    for t in targets:
        out = await _send(t.message)
        print(f"[{t.expected_label:>13}] {t.message}")
        print(f"               -> {out.get('reply', '')[:160]}")
        print(f"               trace={out.get('trace_id')}\n")


if __name__ == "__main__":
    asyncio.run(main())
