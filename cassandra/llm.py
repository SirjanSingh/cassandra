"""Thin Gemini 3 helper shared by the sub-agents.

Kept tiny on purpose: ADK wires the agents (see loop_agent.py); the sub-agent
*logic* just needs structured Gemini calls, so we isolate them here for testability.
"""

from __future__ import annotations

import asyncio
import json
import random
from typing import TypeVar

from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from openai import AsyncOpenAI
from pydantic import BaseModel

from .config import get_settings

T = TypeVar("T", bound=BaseModel)


async def _gen_with_retry(call, *, attempts: int = 7, base_delay: float = 4.0, max_delay: float = 60.0):
    """Run a Gemini call, backing off on transient 429/503.

    Vertex Gemini throughput is Dynamic Shared Quota (esp. the `global` endpoint):
    it returns 429 RESOURCE_EXHAUSTED under any burst and there is no quota knob to
    raise. The SDK's own retry gives up quickly, so we ride it out with exponential
    backoff + jitter — jitter is important so parallel calls don't retry in lockstep
    and re-collide on the same shared pool. This is the supported way to live on DSQ.
    """
    for i in range(attempts):
        try:
            return await call()
        except (genai_errors.ClientError, genai_errors.ServerError) as exc:
            code = getattr(exc, "code", None)
            if code not in (429, 503) or i == attempts - 1:
                raise
            delay = min(base_delay * (2**i), max_delay)
            await asyncio.sleep(delay + random.uniform(0, delay * 0.25))


def _client() -> genai.Client:
    s = get_settings()
    if s.google_genai_use_vertexai:
        return genai.Client(
            vertexai=True,
            project=s.google_cloud_project,
            location=s.google_cloud_location,
        )
    return genai.Client(
        vertexai=False,
        api_key=s.gemini_api_key,
    )


def _openai_client() -> AsyncOpenAI:
    s = get_settings()
    if s.is_openai:
        return AsyncOpenAI(api_key=s.openai_api_key)
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=s.gemini_api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/SirjanSingh/cassandra",
            "X-Title": "Cassandra",
        },
    )


async def structured(
    prompt: str, schema: type[T], *, system: str = "", temperature: float = 0.2
) -> T:
    """Ask Gemini 3 / OpenRouter / OpenAI for a response that parses into `schema` (Pydantic).

    `temperature` defaults to 0.2; classifiers (e.g. the Diagnostician's LLM-as-judge) pass
    0.0 so the same agent turn gets the same verdict run-to-run (deterministic supervision).
    """
    s = get_settings()
    if s.is_openai or s.is_openrouter:
        client = _openai_client()
        model = s.openai_model if s.is_openai else s.gemini_model
        sys_instr = (system + "\n\nIMPORTANT: Be extremely concise. Respond with minimal reasoning/text to fit within token limits.") if system else "IMPORTANT: Be extremely concise. Respond with minimal reasoning/text to fit within token limits."
        resp = await client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": sys_instr},
                {"role": "user", "content": prompt},
            ],
            response_format=schema,
            temperature=temperature,
        )
        parsed = resp.choices[0].message.parsed
        if parsed is None:
            raise ValueError("Failed to parse response from OpenAI/OpenRouter model")
        return parsed

    resp = await _gen_with_retry(
        lambda: _client().aio.models.generate_content(
            model=s.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system or None,
                response_mime_type="application/json",
                response_schema=schema.model_json_schema(),
                temperature=temperature,
            ),
        )
    )
    return schema.model_validate(json.loads(resp.text))


async def text(prompt: str, *, system: str = "", temperature: float = 0.3) -> str:
    s = get_settings()
    if s.is_openai or s.is_openrouter:
        client = _openai_client()
        model = s.openai_model if s.is_openai else s.gemini_model
        sys_instr = (system + "\n\nIMPORTANT: Be extremely concise. Respond with minimal reasoning/text to fit within token limits.") if system else "IMPORTANT: Be extremely concise. Respond with minimal reasoning/text to fit within token limits."
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": sys_instr},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    resp = await _gen_with_retry(
        lambda: _client().aio.models.generate_content(
            model=s.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system or None, temperature=temperature
            ),
        )
    )
    return resp.text or ""
