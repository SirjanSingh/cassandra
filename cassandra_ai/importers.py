"""Turn whole conversations into checkable `Turn`s.

Most bots log OpenAI-style chat messages: `system` / `user` / `assistant` messages, with
the assistant's `tool_calls` and one `tool` message per result. A conversation becomes one
`Turn` per assistant reply that has text: its question is the latest user message, and
its tool calls are every call made since the previous text reply, each with its result.

Accepted shapes, so a raw export works without a converter script:

* `tool_calls` as a list or as its `str()` (some exporters write Python reprs);
* `function.arguments` as a JSON string or an object;
* `content` as a string, `None`, `"None"` or a list of `{"type": "text", "text": ...}` parts;
* tool results matched to calls by `tool_call_id`, else in order.

Pure: no network, no environment.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from .models import Turn

_CALL_MARKUP = re.compile(r"<function_calls>.*?(?:</function_calls>|$)", re.S)


def _text(content: Any) -> str:
    if isinstance(content, list):
        content = " ".join(p.get("text", "") for p in content
                           if isinstance(p, dict) and p.get("type") in (None, "text"))
    if not isinstance(content, str) or content == "None":
        return ""
    return _CALL_MARKUP.sub("", content).strip()


def _calls(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, "None", ""):
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            try:
                raw = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                return []
    out = []
    for c in raw if isinstance(raw, list) else []:
        if not isinstance(c, dict):
            continue
        fn: dict[str, Any] = c["function"] if isinstance(c.get("function"), dict) else c
        args = fn.get("arguments", fn.get("args"))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"raw": args}
        out.append({"id": c.get("id"), "name": fn.get("name"), "args": args or {}})
    return out


def _result(content: Any) -> Any:
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return content
    return content


def turns_from_messages(messages: list[dict[str, Any]], conv_id: str = "") -> list[Turn]:
    """One `Turn` per assistant reply with text. Never raises on odd messages; skips them."""
    turns: list[Turn] = []
    question = ""
    pending: list[dict[str, Any]] = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "user":
            question = _text(m.get("content")) or question
        elif role == "assistant":
            pending.extend(_calls(m.get("tool_calls")))
            answer = _text(m.get("content"))
            if answer:
                calls = [{"name": c["name"], "args": c["args"], "result": c.get("result")}
                         for c in pending]
                turns.append(Turn(id=f"{conv_id}#{len(turns) + 1}" if conv_id else
                                  str(len(turns) + 1), question=question, answer=answer,
                                  tool_calls=calls))
                pending = []
        elif role in ("tool", "function"):
            call_id = m.get("tool_call_id")
            target = next((c for c in pending if call_id not in (None, "None")
                           and c.get("id") == call_id and "result" not in c), None)
            if target is None:
                target = next((c for c in pending if "result" not in c
                               and c.get("name") in (m.get("name"), None)), None)
            if target is None:  # a result with no logged call: keep it, it is still data
                target = {"id": call_id, "name": m.get("name"), "args": {}}
                pending.append(target)
            target["result"] = _result(m.get("content"))
    return turns


MESSAGE_KEYS = ("messages", "traj", "conversation")


def conversation_messages(row: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The message list of a conversation-shaped row, or None if it isn't one."""
    for key in MESSAGE_KEYS:
        if isinstance(row.get(key), list):
            return row[key]
    return None
