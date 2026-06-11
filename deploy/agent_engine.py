"""Deploy Cassandra to Vertex AI Agent Engine (primary runtime, ARCHITECTURE.md S5).

SPIKE-RECONCILE: confirm the Agent Engine deploy API for the pinned vertexai /
google-adk SDK. If Agent Engine deploy is flaky during submission week, the
documented fallback is to host SupervisionPipeline behind a Cloud Run service and
keep the Cloud Scheduler -> trace_poller path (risk R2).

Usage:
    python -m deploy.agent_engine
"""

import os

from cassandra.config import get_settings

# Agent Engine requires a REGIONAL location (never "global") and a GCS staging
# bucket. AGENT_ENGINE_* env vars take precedence over the (possibly stale) .env
# project so the deploy target is unambiguous.
_PROJECT = os.getenv("AGENT_ENGINE_PROJECT")
_LOCATION = os.getenv("AGENT_ENGINE_LOCATION", "us-central1")
_STAGING_BUCKET = os.getenv("AGENT_ENGINE_STAGING_BUCKET")  # gs://... (auto-derived if unset)


def main() -> None:
    s = get_settings()
    import vertexai  # type: ignore
    from vertexai import agent_engines  # type: ignore
    from vertexai.preview.reasoning_engines import AdkApp  # type: ignore

    from cassandra.loop_agent import build_adk_agent

    project = _PROJECT or s.google_cloud_project
    location = _LOCATION if s.google_cloud_location in ("", "global") else s.google_cloud_location
    bucket = _STAGING_BUCKET or f"gs://{project}-agent-engine"

    print(f"Deploying to Agent Engine: project={project} location={location} staging={bucket}")
    vertexai.init(project=project, location=location, staging_bucket=bucket)
    # Wrap the ADK LoopAgent in AdkApp so the Agent Engine runtime has a servable
    # query interface (a bare LoopAgent boots with nothing to serve -> "cannot
    # serve traffic").
    app = AdkApp(agent=build_adk_agent())
    remote = agent_engines.create(
        app,
        requirements=[
            # The AdkApp is unpickled in the runtime container, so vertexai +
            # cloudpickle must be installed there or it crashes with
            # ModuleNotFoundError: No module named 'vertexai'. Passing an explicit
            # requirements list replaces the defaults, so list them here.
            "google-cloud-aiplatform[agent_engines]>=1.95.0",
            "cloudpickle>=3.0.0",
            "google-genai>=0.3.0",
            "google-adk>=0.1.0",
            "mcp>=1.2.0",
            "google-cloud-firestore>=2.19.0",
            "pydantic>=2.9.0",
            "pydantic-settings>=2.6.0",
            "httpx>=0.27.0",
            "openai>=1.50.0",
        ],
        extra_packages=["cassandra", "patient"],
        display_name="cassandra-meta-agent",
    )
    print(f"Deployed Cassandra to Agent Engine: {remote.resource_name}")


if __name__ == "__main__":
    main()
