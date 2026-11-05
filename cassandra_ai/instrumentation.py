"""Self-tracing: Cassandra's OWN reasoning -> Phoenix `cassandra-meta` project.

Cassandra is an agent that watches agents — so its own LLM calls deserve the same
observability it demands of others. This instruments Cassandra's OpenAI/OpenRouter
reasoning via OpenInference and ships the spans to the `META_PROJECT` Phoenix project,
scoped to a dedicated TracerProvider so it never clobbers the Patient's manual spans.

Combined with the self-evaluation scorecard, this completes the recursive loop the
Arize track rewards: the watcher, fully observable to itself, in Phoenix.

Call `init_self_tracing()` once at startup (dashboard / run_pipeline / mcp server).
Safe + idempotent: any failure (packages missing, Phoenix down) degrades to a no-op.
"""

from __future__ import annotations

from .config import get_settings

_INITIALIZED = False


def init_self_tracing() -> bool:
    """Instrument Cassandra's own LLM calls into META_PROJECT. Returns True if active."""
    global _INITIALIZED
    if _INITIALIZED:
        return True

    s = get_settings()
    if not s.self_trace_enabled:
        return False

    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create(
                {"service.name": "cassandra", "openinference.project.name": s.meta_project}
            )
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=f"{s.phoenix_base_url}/v1/traces",
                    headers={"Authorization": f"Bearer {s.phoenix_api_key}"},
                )
            )
        )
        # Scope auto-instrumentation to this provider so we don't touch the global one.
        OpenAIInstrumentor().instrument(tracer_provider=provider)
        _INITIALIZED = True
        return True
    except Exception as e:  # pragma: no cover - environment-dependent
        print(f"[cassandra] self-tracing disabled ({type(e).__name__}: {e})")
        return False
