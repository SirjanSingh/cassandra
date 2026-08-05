"""Offline stress harness for Cassandra. No network, no LLM, no external services.

Backs the measured numbers in docs/SECURITY_AUDIT.md §3. Safe to run anywhere:
it touches only a scratch directory under scripts/ and never contacts Phoenix,
the Patient, or any LLM provider.

    python scripts/stress_probe.py

Probes the pure/stateful cores that production load would hit:
  1. grounding regex behaviour on adversarial/large answers (ReDoS + precision)
  2. LocalState dedupe-window overflow (the 500 cap) -> incident re-processing
  3. LocalState concurrent-write durability (lost updates / corruption)
  4. Firestore-style read-modify-write lost-update race (simulated, same code shape)
  5. EventBus unbounded-queue growth with a stalled SSE subscriber
  6. Watcher cursor advance vs single-incident-per-cycle (incident loss)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cassandra.events import EventBus
from cassandra.grounding import SHOPBOT_SPEC, check_grounding
from cassandra.models import PipelineEvent, Stage
from cassandra.state import LocalState

OUT: list[str] = []


def say(s: str = "") -> None:
    print(s)
    OUT.append(s)


# ---------- 1. grounding regex under adversarial input ----------
def probe_grounding() -> None:
    say("\n=== 1. GROUNDING: regex cost + precision on adversarial answers ===")
    ledger = [{"name": "get_refund_policy", "args": {"region": "DE"}, "result": {"found": False}}]

    # 1a. cost scaling on large answers (agents can emit long replies)
    for size_kb in (1, 10, 100, 500):
        answer = ("The customer asked about shipping. " * 30) * (size_kb * 1024 // 1000)
        t0 = time.perf_counter()
        check_grounding(answer, ledger, SHOPBOT_SPEC)
        ms = (time.perf_counter() - t0) * 1000
        say(f"  answer {len(answer)//1024:>4} KB -> {ms:8.2f} ms")

    # 1b. pathological input aimed at the eta/month alternation
    evil = "May " + "1" * 5000
    t0 = time.perf_counter()
    check_grounding(evil, ledger, SHOPBOT_SPEC)
    say(f"  pathological 'May 111..' (5KB digits) -> {(time.perf_counter()-t0)*1000:.2f} ms")

    # 1c. PRECISION: does an innocent answer get flagged?
    cases = [
        ("Your order shipped 3 days ago and is on its way.", "innocent shipping remark"),
        ("I can't provide the refund policy right now - orders usually ship within 2 days.",
         "HONEST DECLINE + incidental duration"),
        ("I couldn't find that information.", "clean decline, no numbers"),
        ("Refunds are available within 30 days of purchase.", "genuine unsupported policy claim"),
    ]
    say("  precision checks (ledger = get_refund_policy -> {found:false}):")
    for answer, label in cases:
        v = check_grounding(answer, ledger, SHOPBOT_SPEC)
        cls = "ABSTAIN" if v.abstain else v.failure_class.value.upper()
        say(f"    {cls:<14} <- {label}")

    # 1d. VALUE MISMATCH: successful tool, answer contradicts it
    good_ledger = [{"name": "lookup_order", "args": {"id": "A1"},
                    "result": {"found": True, "carrier": "DHL", "eta": "2026-08-09"}}]
    v = check_grounding("Your order is with UPS, arriving 2026-12-25.", good_ledger, SHOPBOT_SPEC)
    cls = "ABSTAIN" if v.abstain else v.failure_class.value.upper()
    say(f"  value-mismatch (tool says DHL/2026-08-09, answer says UPS/2026-12-25) -> {cls}")


# ---------- 2 + 3. LocalState ----------
def probe_state_window(tmp: Path) -> None:
    say("\n=== 2. STATE: dedupe window overflow (mark_seen keeps last 500) ===")
    p = tmp / "s1.json"
    st = LocalState(p)
    first = "span-0000"
    st.mark_seen(first)
    for i in range(1, 600):
        st.mark_seen(f"span-{i:04d}")
    say(f"  marked 600 spans; seen('{first}') = {st.seen(first)}  <- False means re-processing")
    say(f"  retained entries: {len(json.loads(p.read_text())['seen'])}")

    # cost of the linear scan
    t0 = time.perf_counter()
    for _ in range(1000):
        st.seen("span-0599")
    say(f"  1000x seen() list-scan: {(time.perf_counter()-t0)*1000:.1f} ms")

    # write amplification: full rewrite per mark
    t0 = time.perf_counter()
    for i in range(200):
        st.mark_seen(f"burst-{i}")
    say(f"  200x mark_seen (full file rewrite each): {(time.perf_counter()-t0)*1000:.1f} ms")


def probe_state_concurrency(tmp: Path) -> None:
    say("\n=== 3. STATE: two instances sharing one backing file (Cloud Run >1 instance) ===")
    p = tmp / "s2.json"
    p.write_text(json.dumps({"seen": []}))
    a, b = LocalState(p), LocalState(p)   # two processes/instances
    a.mark_seen("span-A")
    b.mark_seen("span-B")                 # b's in-memory copy never saw span-A
    final = json.loads(p.read_text())["seen"]
    say(f"  A marked span-A, B marked span-B -> file now: {final}")
    say(f"  span-A survived: {'span-A' in final}  <- False = LOST UPDATE, A's incident reruns")


def probe_firestore_race() -> None:
    say("\n=== 4. STATE: Firestore read-modify-write race (same code shape, simulated) ===")
    doc = {"seen": []}

    async def instance(name: str, delay: float) -> None:
        snap = list(doc.get("seen", []))      # _get()
        await asyncio.sleep(delay)            # network round-trip window
        doc["seen"] = ([*snap, name])[-500:]  # .set(merge=True) overwrites the array

    async def race() -> None:
        await asyncio.gather(instance("span-A", 0.02), instance("span-B", 0.01))

    asyncio.run(race())
    say(f"  concurrent mark_seen -> {doc['seen']}")
    say(f"  both retained: {len(doc['seen']) == 2}  <- False = duplicate supervision + LLM spend")


# ---------- 5. EventBus backpressure ----------
def probe_eventbus() -> None:
    say("\n=== 5. EVENTS: unbounded queue growth with a stalled SSE subscriber ===")

    async def main() -> None:
        bus = EventBus()
        started = asyncio.Event()

        async def stalled_client() -> None:
            agen = bus.subscribe()
            started.set()
            await agen.__anext__()      # take exactly one, then never drain again
            await asyncio.sleep(3600)

        task = asyncio.create_task(stalled_client())
        await started.wait()
        await asyncio.sleep(0.05)

        tracemalloc.start()
        base = tracemalloc.get_traced_memory()[0]
        # DISTINCT events: publishing one shared object measures only the queue
        # slots and badly understates real retention.
        n = 20000
        t0 = time.perf_counter()
        for i in range(n):
            await bus.publish(PipelineEvent(
                incident_id=f"inc-{i}", stage=Stage.WATCHED, title=f"t{i}",
                detail="d" * 2000, payload={"blob": "y" * 2000}))
        grew = tracemalloc.get_traced_memory()[0] - base
        tracemalloc.stop()
        q = bus._subscribers[0]
        say(f"  published {n} distinct events to a stalled subscriber in "
            f"{(time.perf_counter()-t0)*1000:.0f} ms")
        say(f"  queue depth now: {q.qsize()}  (unbounded: no backpressure, no drop)")
        say(f"  traced heap growth: {grew/1024/1024:.1f} MB -> {grew/n:.0f} bytes/event")
        say(f"  -> one stalled SSE client at 1 event/sec costs "
            f"~{grew/n*3600/1024/1024:.0f} MB/hr, unbounded")
        task.cancel()

    asyncio.run(main())


# ---------- 6. watcher cursor vs one-incident-per-cycle ----------
def probe_incident_loss() -> None:
    say("\n=== 6. PIPELINE: cursor advances past incidents the cycle never processes ===")
    now = datetime.now(timezone.utc)
    batch = [("span-A", now), ("span-B", now + timedelta(seconds=1)),
             ("span-C", now + timedelta(seconds=2))]
    # watcher.poll(): cursor := max(started_at) over ALL returned spans
    cursor = max(ts for _, ts in batch)
    # loop_agent.run_once(): diagnose in order, return after the FIRST failure (span-B)
    processed, marked_seen = "span-B", {"span-A", "span-B"}
    survivors = [sid for sid, ts in batch if sid not in marked_seen]
    still_visible = [sid for sid, ts in batch if sid not in marked_seen and ts > cursor]
    say(f"  batch: {[s for s, _ in batch]}; processed this cycle: {processed}")
    say(f"  cursor advanced to newest span ({cursor.isoformat()})")
    say(f"  never diagnosed / never marked seen: {survivors}")
    say(f"  still returned by the next poll (started_at > cursor): {still_visible}")
    say(f"  -> {len(survivors)} incident(s) permanently dropped per burst")


if __name__ == "__main__":
    import shutil
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="cassandra-stress-"))
    try:
        probe_grounding()
        probe_state_window(tmp)
        probe_state_concurrency(tmp)
        probe_firestore_race()
        probe_eventbus()
        probe_incident_loss()
        say("\nDONE")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
