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

    @property
    def model_provider(self) -> str:
        """Phoenix `upsert-prompt` model_provider for the ACTIVE backend.

        OpenRouter speaks the OpenAI wire protocol, so it registers as OPENAI too.
        Falls back to GOOGLE (Vertex/Gemini). Used so prompt versions are tagged with
        the provider that actually produced them (NFR-10).
        """
        if self.is_openai or self.is_openrouter:
            return "OPENAI"
        return "GOOGLE"

    @property
    def model_name(self) -> str:
        """The model id for the ACTIVE backend (OpenAI vs Gemini/OpenRouter)."""
        return self.openai_model if self.is_openai else self.gemini_model


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Re-read .env and rebuild the cached Settings.

    `get_settings()` is cached for the process lifetime, and `load_dotenv` only runs at
    import — so editing `.env` does not take effect until restart (this bit us when adding
    the OpenAI key). Long-running servers should still be restarted, but this gives scripts
    and tests a way to pick up a changed `.env` without a fresh process.
    """
    get_settings.cache_clear()
    load_dotenv(override=True)
    return get_settings()
