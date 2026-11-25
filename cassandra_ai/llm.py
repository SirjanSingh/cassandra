"""The one place Cassandra calls an LLM: any OpenAI-compatible chat endpoint.

`openai` is an optional dependency (`pip install "cassandra-ai[llm]"`) so the offline
checks install in seconds. The request shape (system suffix, strict schema parsing,
temperature 0) is exactly what produced the RAGTruth numbers in poc/ragtruth — change it
and re-run that benchmark.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from .config import get_settings

T = TypeVar("T", bound=BaseModel)

_CONCISE = ("IMPORTANT: Be extremely concise. Respond with minimal reasoning/text to fit "
            "within token limits.")


class LLMUnavailable(RuntimeError):
    """No usable LLM: package missing or no key / endpoint configured."""


def _client():
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as e:
        raise LLMUnavailable(
            'The claim check needs the LLM extra: pip install "cassandra-ai[llm]"') from e
    s = get_settings()
    if not s.llm_configured:
        raise LLMUnavailable(
            "No LLM configured: set OPENAI_API_KEY (and OPENAI_BASE_URL for a non-OpenAI "
            "endpoint such as OpenRouter, Azure or a local Ollama server).")
    # The SDK retries 429/5xx with backoff; give it room for rate-limited batch scans.
    return AsyncOpenAI(api_key=s.openai_api_key or "not-needed", base_url=s.openai_base_url,
                       max_retries=6)


def describe() -> str:
    """Human-readable 'model @ endpoint' for reports and consent messages."""
    s = get_settings()
    return f"{s.model} @ {s.openai_base_url or 'api.openai.com'}"


async def structured(prompt: str, schema: type[T], *, system: str = "",
                     temperature: float = 0.0) -> T:
    """Ask the model for a reply that parses into `schema`."""
    client = _client()
    resp = await client.beta.chat.completions.parse(
        model=get_settings().model,
        messages=[
            {"role": "system", "content": f"{system}\n\n{_CONCISE}" if system else _CONCISE},
            {"role": "user", "content": prompt},
        ],
        response_format=schema,
        temperature=temperature,
    )
    parsed = resp.choices[0].message.parsed
    if parsed is None:
        raise ValueError("The model's reply did not parse into the expected JSON schema")
    return parsed
