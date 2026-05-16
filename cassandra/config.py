"""Central typed configuration. All env access goes through here (NFR-4)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Google Cloud / Gemini 3
    google_cloud_project: str = "your-gcp-project-id"
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True
    gemini_model: str = "gemini-3-pro"  # SPIKE-RECONCILE: confirm exact id in region

    # Arize Phoenix (partner MCP)
    phoenix_base_url: str = "https://app.phoenix.arize.com"
    phoenix_api_key: str = "replace-me"
    phoenix_mcp_command: str = "npx"
    phoenix_mcp_args: str = "-y,@arizeai/phoenix-mcp@latest"
    patient_project: str = "patient-prod"
    meta_project: str = "cassandra-meta"

    # Cassandra tuning
    poll_interval_seconds: int = 60
    diagnosis_confidence_threshold: float = 0.7
    synth_dataset_size: int = 12

    # State backend
    state_backend: str = "firestore"  # firestore | gcs | local
    firestore_collection: str = "cassandra_state"

    # Dashboard
    dashboard_port: int = 8080
    patient_endpoint: str = "http://localhost:8081/chat"

    @property
    def phoenix_mcp_arg_list(self) -> list[str]:
        return [a for a in self.phoenix_mcp_args.split(",") if a]


@lru_cache
def get_settings() -> Settings:
    return Settings()
