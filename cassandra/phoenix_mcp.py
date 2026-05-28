"""The single gateway to Arize Phoenix via its MCP server (NFR-10).

This is the ONLY module that talks MCP. Every Phoenix tool family Cassandra needs
(spans, annotations, datasets, experiments, prompts - REQUIREMENTS.md S4) is exposed
as a typed async method here.

Reconciled against actual @arizeai/phoenix-mcp surface (spike_output/phoenix_mcp_tools.json).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import Settings, get_settings
from .models import DatasetExample, SpanRecord

# Reconciled tool names from spike_output/phoenix_mcp_tools.json
_TOOLS = {
    "list_projects": "list-projects",
    "query_spans": "get-spans",
    "add_examples": "add-dataset-examples",
    "get_experiment": "get-experiment-by-id",
    "create_prompt_version": "upsert-prompt",
    "get_prompt": "get-prompt",
    "list_traces": "list-traces",
}


class PhoenixMCP:
    """Async wrapper around a stdio MCP session to @arizeai/phoenix-mcp."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.s = settings or get_settings()
        self._session: ClientSession | None = None

    @asynccontextmanager
    async def session(self):
        """Open a stdio MCP session. Phoenix creds passed via env to the server."""
        params = StdioServerParameters(
            command=self.s.phoenix_mcp_command,
            args=self.s.phoenix_mcp_arg_list,
            env={
                "PHOENIX_API_KEY": self.s.phoenix_api_key,
                "PHOENIX_BASE_URL": self.s.phoenix_base_url,
            },
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._session = session
                try:
                    yield self
                finally:
                    self._session = None

    async def _call(self, tool_key: str, **arguments: Any) -> Any:
        if self._session is None:
            raise RuntimeError("PhoenixMCP used outside `async with .session()`")
        tool_name = _TOOLS[tool_key]
        result = await self._session.call_tool(tool_name, arguments=arguments)
        return _unwrap(result)

    # --- introspection ---

    async def list_tools(self) -> list[dict]:
        if self._session is None:
            raise RuntimeError("PhoenixMCP used outside `async with .session()`")
        tools = await self._session.list_tools()
        return [
            {"name": t.name, "description": t.description, "schema": t.inputSchema}
            for t in tools.tools
        ]

    async def list_projects(self) -> list[dict]:
        return _as_list(await self._call("list_projects"))

    # --- Watcher (FR-W2): get-spans uses project_identifier ---

    async def query_spans(
        self, project: str, since: datetime | None, limit: int = 50
    ) -> list[SpanRecord]:
        kwargs: dict[str, Any] = {
            "project_identifier": project,
            "limit": limit,
        }
        if since:
            kwargs["start_time"] = since.isoformat()
        raw = await self._call("query_spans", **kwargs)
        items = _as_list(raw)
        return [normalize_span(r, project) for r in items if isinstance(r, dict)]

    # --- Diagnostician (FR-D3): add-span-annotations ---

    async def annotate_span(
        self, span_id: str, label: str, score: float, explanation: str
    ) -> str:
        """Write a Cassandra annotation on the given span."""
        if self._session is None:
            raise RuntimeError("PhoenixMCP used outside `async with .session()`")
        res = await self._session.call_tool(
            "add-span-annotations",
            arguments={
                "span_ids": [span_id],
                "annotations": [
                    {
                        "name": "cassandra",
                        "label": label,
                        "score": score,
                        "explanation": explanation,
                        "annotator_kind": "LLM",
                    }
                ],
            },
        )
        return _id_of(_unwrap(res), fallback=f"ann-{span_id}")

    # --- Synthesizer (FR-S2): add-dataset-examples creates the dataset on first call ---

    async def create_dataset(self, name: str, description: str) -> str:
        """Return the dataset name — Phoenix MCP creates it implicitly on first add."""
        return name

    async def add_examples(self, dataset_id: str, examples: list[DatasetExample]) -> int:
        rows = [
            {
                "input": {"question": e.input_text},
                "output": {"expected": e.expected_answer},
                "metadata": {"acceptance": e.acceptance_criterion},
            }
            for e in examples
        ]
        await self._call("add_examples", dataset_name=dataset_id, examples=rows)
        return len(rows)

    # --- Evaluator (FR-E1/E3/E4) ---

    async def get_experiment(self, experiment_id: str) -> dict:
        return _as_dict(await self._call("get_experiment", experiment_id=experiment_id))

    # Phoenix MCP doesn't expose create/run experiment tools yet — stubs for now.
    async def create_experiment(self, dataset_id: str, name: str, prompt: str) -> str:
        return f"experiment-{name}"

    async def run_experiment(self, experiment_id: str) -> dict:
        return {"status": "queued", "experiment_id": experiment_id}

    # --- Patcher (FR-PA2): upsert-prompt ---

    async def create_prompt_version(
        self, name: str, prompt_text: str, metadata: dict
    ) -> str:
        res = await self._call(
            "create_prompt_version",
            name=name,
            template=prompt_text,
            model_provider="GOOGLE",
            model_name=self.s.gemini_model,
        )
        return _id_of(res, fallback=f"{name}-v?")

    def span_url(self, span: SpanRecord) -> str:
        """Deep link into the Phoenix UI for the dashboard (FR-DB4)."""
        return f"{self.s.phoenix_base_url}/projects/{span.project}/spans/{span.span_id}"


# --- normalization & unwrap helpers ---


def normalize_span(raw: dict, project: str) -> SpanRecord:
    """Map a real Phoenix MCP span dict to our SpanRecord.

    Real schema from get-spans (spike_output/phoenix_mcp_tools.json):
    {
      "id": "span123",
      "context": {"trace_id": "...", "span_id": "..."},
      "start_time": "2024-01-01T12:00:00Z",
      "attributes": {"input.value": "...", "output.value": "..."}
    }
    """
    ctx = raw.get("context", {})
    span_id = str(raw.get("id") or ctx.get("span_id", ""))
    trace_id = str(raw.get("trace_id") or ctx.get("trace_id", ""))
    attrs = raw.get("attributes", {})
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except json.JSONDecodeError:
            attrs = {}

    return SpanRecord(
        span_id=span_id,
        trace_id=trace_id,
        project=project,
        started_at=_parse_dt(raw.get("start_time")),
        input_text=_flat_str(attrs, "input.value") or _flat_str(attrs, "llm.input_messages"),
        output_text=_flat_str(attrs, "output.value") or _flat_str(attrs, "llm.output_messages"),
        session_id=_flat_str(attrs, "patient.session_id") or "demo",
        tool_calls=raw.get("tool_calls", []),
        raw=raw,
    )


def _unwrap(result: Any) -> Any:
    """MCP tool results arrive as content blocks; pull out JSON/text payload."""
    content = getattr(result, "content", result)
    if isinstance(content, list):
        for block in content:
            text = getattr(block, "text", None)
            if text is not None:
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return text
    return content


def _as_list(v: Any) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, dict):
        for key in ("data", "results", "items", "spans", "projects"):
            if isinstance(v.get(key), list):
                return v[key]
    return [v] if v else []


def _as_dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {"value": v}


def _id_of(v: Any, fallback: str) -> str:
    if isinstance(v, dict):
        for key in ("id", "dataset_id", "experiment_id", "annotation_id", "version_id"):
            if v.get(key):
                return str(v[key])
    return str(v) if isinstance(v, (str, int)) else fallback


def _parse_dt(v: Any) -> datetime:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.now()


def _flat_str(d: dict, key: str) -> str:
    """Pull a flat dotted key from an attributes dict."""
    val = d.get(key)
    if not val:
        return ""
    return val if isinstance(val, str) else json.dumps(val)[:4000]
