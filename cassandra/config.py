"""Central typed configuration. All env access goes through here (NFR-4)."""

from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Google Cloud / Gemini 3
    google_cloud_project: str = "your-gcp-project-id"
    google_cloud_location: str = "us-central1"
    google_genai_use_vertexai: bool = True
    gemini_model: str = "gemini-3-pro"  # SPIKE-RECONCILE: confirm exact id in region
    gemini_api_key: str | None = None

    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

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

    # Introspection / on-product depth
    self_trace_enabled: bool = True       # trace Cassandra's own reasoning into META_PROJECT
    phoenix_experiments_enabled: bool = False  # also register A/B as a real Phoenix experiment

    # State backend
    state_backend: str = "firestore"  # firestore | gcs | local
    firestore_collection: str = "cassandra_state"

    # Dashboard (defaults match the documented local ports; .env overrides)
    dashboard_port: int = 8085
    patient_endpoint: str = "http://localhost:8082/chat"

    @property
    def phoenix_mcp_arg_list(self) -> list[str]:
        return [a for a in self.phoenix_mcp_args.split(",") if a]

    @property
    def is_openrouter(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_api_key.startswith("sk-or-"))

    @property
    def is_openai(self) -> bool:
        return bool(self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
