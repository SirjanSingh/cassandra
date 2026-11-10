"""Check each answer before it reaches the customer.

    pip install "cassandra-ai[llm]"   # and set OPENAI_API_KEY (or OPENAI_BASE_URL)
    python examples/check_live.py
"""

import asyncio

import cassandra


async def main() -> None:
    result = await cassandra.check(
        answer="Your order ships Friday via FedEx.",
        question="Where is my order?",
        tool_calls=[{"name": "lookup_order", "args": {"order_id": "A1"},
                     "result": {"found": True, "carrier": "UPS", "eta": "2026-11-20"}}],
    )
    print(result.verdict)  # "flagged"
    for f in result.findings:
        print(f"- [{f.layer}] {f.kind}: {f.claim}  ({f.detail})")
    # In a real bot: if result.verdict == "flagged", send the answer to a human, or
    # regenerate it with the findings as feedback.


asyncio.run(main())
