"""Baseline-prompt resolution: where the supervised agent's CURRENT prompt comes from.

The supervision loop needs the supervised agent's current ("baseline") system prompt
twice: the Evaluator scores it against the synthesized dataset, and the Patcher diffs
the candidate against it. The bundled demo Patient (ShopBot) exposes it as a Python
constant, but a third-party agent has no module Cassandra can import — so resolution
is a chain (first hit wins):

1. ``BASELINE_PROMPT_FILE`` — a file the operator points at (any agent, zero code).
2. The failing span itself — the OpenInference ``llm.input_messages`` system message,
   when the agent's tracing records its prompt (zero config).
3. The bundled demo Patient's ``FRAGILE_SYSTEM_PROMPT``, when importable (demo mode).

This module is what makes the closed loop agent-agnostic: nothing else in the
pipeline may import from ``patient/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import get_settings
from .models import SpanRecord


class BaselinePromptError(RuntimeError):
    """No source could provide the supervised agent's baseline system prompt."""


def resolve_baseline_prompt(span: SpanRecord | None = None) -> str:
    """Resolve the supervised agent's current system prompt (see module docstring)."""
    s = get_settings()
    if s.baseline_prompt_file:
        text = Path(s.baseline_prompt_file).read_text(encoding="utf-8").strip()
        if text:
            return text
    if span is not None:
        from_span = _system_prompt_from_span(span)
        if from_span:
            return from_span
    try:
        from patient.agent import FRAGILE_SYSTEM_PROMPT

        return FRAGILE_SYSTEM_PROMPT
    except ImportError:
        pass
    raise BaselinePromptError(
        "Cannot determine the supervised agent's baseline system prompt. Either set "
        "BASELINE_PROMPT_FILE to a file containing it, or instrument the agent so its "
        "spans record llm.input_messages with a system-role message."
    )


def _system_prompt_from_span(span: SpanRecord) -> str:
    """Extract the system message from an OpenInference span's llm.input_messages.

    Phoenix MCP builds disagree on attribute shape, so we accept all three:
    a real list of message dicts, a JSON-encoded string of the same, and flat
    dotted keys (``llm.input_messages.0.message.role``).
    """
    attrs = span.raw.get("attributes", {})
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except json.JSONDecodeError:
            return ""
    if not isinstance(attrs, dict):
        return ""

    msgs = attrs.get("llm.input_messages")
    if msgs is None and isinstance(attrs.get("llm"), dict):
        msgs = attrs["llm"].get("input_messages")
    if isinstance(msgs, str):
        try:
            msgs = json.loads(msgs)
        except json.JSONDecodeError:
            msgs = None
    if isinstance(msgs, list):
        for m in msgs:
            if not isinstance(m, dict):
                continue
            inner = m.get("message", m)
            if isinstance(inner, dict) and inner.get("role") == "system":
                content = inner.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    for i in range(8):
        if attrs.get(f"llm.input_messages.{i}.message.role") == "system":
            content = attrs.get(f"llm.input_messages.{i}.message.content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""
