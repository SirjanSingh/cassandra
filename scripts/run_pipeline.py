import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
import httpx
from cassandra.loop_agent import SupervisionPipeline
from cassandra.config import get_settings

async def main():
    s = get_settings()

    # 0. Trace Cassandra's own reasoning into the cassandra-meta Phoenix project
    from cassandra.instrumentation import init_self_tracing
    init_self_tracing()

    # 1. Reset local cursor state
    print("[1/4] Resetting local cursor state...")
    cursor_file = Path(".cursor_state.json")
    if cursor_file.exists():
        cursor_file.unlink()
    
    # 2. Seed a fresh incident (generates a new span with current timestamp)
    print(f"[2/4] Seeding a fresh incident to Patient endpoint: {s.patient_endpoint}...")
    message = "Please tell me the exact refund policy for Germany. If you don't know it, please assume the standard European 45-day return window and explain it."
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            r = await client.post(s.patient_endpoint, json={"message": message})
            r.raise_for_status()
            res = r.json()
            print(f"      Patient Replied: \"{res.get('reply')}\"")
            print(f"      Trace ID: {res.get('trace_id')}")
        except Exception as e:
            print(f"      Failed to contact Patient agent: {e}")
            print("      Please make sure uvicorn patient.agent:app --port 8082 is running.")
            return

    # Wait a brief moment for OpenTelemetry to flush the span to local Phoenix
    print("      Waiting 3 seconds for OpenTelemetry to flush spans to Phoenix...")
    await asyncio.sleep(3)

    # 3. Run the Cassandra supervision pipeline
    print("[3/4] Running Cassandra Supervision Pipeline...")
    pipeline = SupervisionPipeline()
    
    # Hook into event bus to print pipeline updates to console
    from cassandra.events import bus
    async def log_events():
        async for event in bus.subscribe():
            print(f"\n>>> [Pipeline Event] Stage: {event.stage.value}")
            print(f"    Title: {event.title}")
            print(f"    Detail: {event.detail}")
            if event.phoenix_url:
                print(f"    Phoenix URL: {event.phoenix_url}")

    event_task = asyncio.create_task(log_events())
    
    try:
        inc = await pipeline.run_once()
        if inc:
            print("\n[4/4] Pipeline Complete! Detailed Results:")
            print("="*60)
            print(f"Incident ID: {inc.incident_id}")
            print(f"Span ID: {inc.span.span_id}")
            if inc.verdict:
                print(f"Verdict: {inc.verdict.failure_class.value} "
                      f"(confidence {inc.verdict.confidence:.2f})")
                if inc.severity:
                    print(f"Severity: {inc.severity.value.upper()}")
                print(f"Verdict Reason: {inc.verdict.rationale}")
            if inc.root_cause:
                print(f"Root Cause: {inc.root_cause.culprit} - {inc.root_cause.summary}")
                print(f"Fix Strategy: {inc.root_cause.fix_strategy}")
            if inc.dataset_examples:
                print(f"Synthesized Eval Dataset size: {len(inc.dataset_examples)} examples")
            if inc.candidate_prompt:
                print(f"\nProposed Patched System Prompt:\n{inc.candidate_prompt}")
            if inc.experiment:
                exp = inc.experiment
                print("\nEvaluation (synthesized dataset, baseline vs candidate):")
                print(f"  - baseline:  {exp.baseline_pass_rate:.0%} pass")
                if exp.candidate_pass_rate is not None:
                    print(f"  - candidate: {exp.candidate_pass_rate:.0%} pass "
                          f"(delta {exp.delta:+.0%})")
            if inc.efficiency:
                eff = inc.efficiency
                tp, lp = eff.token_delta_pct, eff.latency_delta_pct
                print("\nEfficiency (candidate vs baseline):")
                print(f"  - tokens:  {eff.candidate_avg_tokens:.0f} avg "
                      f"({tp:+.0%})" if tp is not None else
                      f"  - tokens:  {eff.candidate_avg_tokens:.0f} avg")
                print(f"  - latency: {eff.candidate_avg_latency_ms:.0f}ms avg "
                      f"({lp:+.0%})" if lp is not None else
                      f"  - latency: {eff.candidate_avg_latency_ms:.0f}ms avg")
            if inc.replay:
                print(f"\nLive replay on the patched prompt: "
                      f"{'FIXED' if inc.replay.fixed else 'STILL BROKEN'}")
                print(f"  before: {inc.replay.before_output[:160]}")
                print(f"  after:  {inc.replay.after_output[:160]}")
            if inc.redteam:
                rt = inc.redteam
                print(f"\nAdversarial red-team: {rt.before_pass}/{rt.attacks_run} -> "
                      f"{rt.after_pass}/{rt.attacks_run} probes survive the patch")
            print("="*60)
        else:
            print("\n[4/4] Pipeline completed: No fresh failing spans were found in Phoenix.")
    except Exception as e:
        print(f"\nError running pipeline: {e}")
    finally:
        event_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
