import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
import httpx
from cassandra.loop_agent import SupervisionPipeline
from cassandra.config import get_settings

async def main():
    s = get_settings()
    
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
            print(f"Verdict Failure: {inc.verdict.is_failure if inc.verdict else False}")
            print(f"Verdict Reason: {inc.verdict.explanation if inc.verdict else 'N/A'}")
            if inc.root_cause:
                print(f"Root Cause: {inc.root_cause}")
            if inc.synth_examples:
                print(f"Synthesized Eval Dataset size: {len(inc.synth_examples)} examples")
            if inc.candidate_prompt:
                print(f"\nProposed Patched System Prompt:\n{inc.candidate_prompt}")
            if inc.eval_runs:
                print("\nEvaluation Runs:")
                for variant, score in inc.eval_runs.items():
                    print(f"  - {variant}: {score}")
            print("="*60)
        else:
            print("\n[4/4] Pipeline completed: No fresh failing spans were found in Phoenix.")
    except Exception as e:
        print(f"\nError running pipeline: {e}")
    finally:
        event_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
