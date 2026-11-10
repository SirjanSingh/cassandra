"""Typed settings. All environment access goes through `get_settings()`.

Precedence: real environment variables, then `.env` in the working directory, then the
defaults below. (The old pipeline let `.env` override the shell, which silently ignored
`OPENAI_MODEL=... cassandra ...`; that is gone.)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Any OpenAI-compatible endpoint: OpenAI, Azure OpenAI, OpenRouter, a local
    # Ollama / vLLM server. Leave the base URL unset for api.openai.com.
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    model: str = Field(default="gpt-4o-mini",
                       validation_alias=AliasChoices("CASSANDRA_MODEL", "OPENAI_MODEL"))

    concurrency: int = Field(default=8, validation_alias="CASSANDRA_CONCURRENCY")

    # `cassandra serve`: require `Authorization: Bearer <key>` when set.
    api_key: str | None = Field(default=None, validation_alias="CASSANDRA_API_KEY")
    # `cassandra serve`: optional tool-call spec applied to every request.
    spec_file: str | None = Field(default=None, validation_alias="CASSANDRA_SPEC_FILE")

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key) or bool(self.openai_base_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached for the process. Call `reload_settings()` after changing the environment."""
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
