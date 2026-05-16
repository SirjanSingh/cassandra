"""Deploy Cassandra to Vertex AI Agent Engine (primary runtime, ARCHITECTURE.md S5).

SPIKE-RECONCILE: confirm the Agent Engine deploy API for the pinned vertexai /
google-adk SDK. If Agent Engine deploy is flaky during submission week, the
documented fallback is to host SupervisionPipeline behind a Cloud Run service and
keep the Cloud Scheduler -> trace_poller path (risk R2).

Usage:
    python -m deploy.agent_engine
"""

from __future__ import annotations

from cassandra.config import get_settings


def main() -> None:
    s = get_settings()
    import vertexai  # type: ignore
    from vertexai import agent_engines  # type: ignore

    from cassandra.loop_agent import build_adk_agent

    vertexai.init(project=s.google_cloud_project, location=s.google_cloud_location)
    remote = agent_engines.create(
        build_adk_agent(),
        requirements=[
            "google-genai>=0.3.0",
            "google-adk>=0.1.0",
            "mcp>=1.2.0",
            "google-cloud-firestore>=2.19.0",
            "pydantic>=2.9.0",
            "pydantic-settings>=2.6.0",
            "httpx>=0.27.0",
        ],
        display_name="cassandra-meta-agent",
    )
    print(f"Deployed Cassandra to Agent Engine: {remote.resource_name}")


if __name__ == "__main__":
    main()
