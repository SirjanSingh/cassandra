"""OpenInference / OTLP wiring so the Patient's spans land in Phoenix (FR-P4).

Call `init_tracing()` once at startup. After that, the manual spans emitted in
agent.py are exported to the Phoenix `patient-prod` project.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from cassandra.config import get_settings

_INITIALIZED = False


def init_tracing(project: str | None = None) -> trace.Tracer:
    """Idempotently configure the OTLP exporter pointed at Phoenix."""
    global _INITIALIZED
    s = get_settings()
    project = project or s.patient_project

    if not _INITIALIZED:
        provider = TracerProvider(
            resource=Resource.create(
                {"service.name": "patient", "openinference.project.name": project}
            )
        )
        # SPIKE-RECONCILE: confirm Phoenix OTLP collector path/headers for your space.
        exporter = OTLPSpanExporter(
            endpoint=f"{s.phoenix_base_url}/v1/traces",
            headers={"Authorization": f"Bearer {s.phoenix_api_key}"},
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _INITIALIZED = True

    return trace.get_tracer("patient")
