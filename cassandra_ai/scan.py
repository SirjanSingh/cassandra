"""Read a bot's exported chat logs (JSONL, one turn per line) into `Turn`s.

    {"id": "t1", "question": "...", "answer": "...",
     "tool_calls": [{"name": "...", "args": {...}, "result": {...}}],
     "context": "retrieved text, a list of passages, or a JSON object"}

Aliases accepted: question = input / user / message; answer = output / reply / response;
tool_calls = tools; context = documents / retrieved / sources.

A line can also be a whole conversation in OpenAI chat format,
`{"id": "c1", "messages": [{"role": "user", ...}, {"role": "assistant", ...}, ...]}`
(`traj` and `conversation` work too); it becomes one turn per assistant reply (see
importers.py). A `.json` file holding a list of such objects is read the same way.
"""

from __future__ import annotations

import json
from pathlib import Path

from .importers import conversation_messages, turns_from_messages
from .models import Turn

_QUESTION_KEYS = ("question", "input", "user", "message")
_ANSWER_KEYS = ("answer", "output", "reply", "response")
_CONTEXT_KEYS = ("context", "documents", "retrieved", "sources")


def _first(row: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if isinstance(row.get(k), str):
            return row[k]
    return None


def parse_row(row: dict, n: int | str = "") -> Turn:
    """One exported turn → Turn. Raises ValueError with the reason."""
    answer = _first(row, _ANSWER_KEYS)
    if answer is None:
        raise ValueError(f"no answer field (expected one of {', '.join(_ANSWER_KEYS)})")
    calls = row.get("tool_calls", row.get("tools"))
    if calls is None:
        calls = []
    if not isinstance(calls, list):
        raise ValueError("tool_calls must be a list")
    context = next((row[k] for k in _CONTEXT_KEYS if row.get(k) not in (None, "", [])), None)
    return Turn(id=str(row.get("id", n)), question=_first(row, _QUESTION_KEYS) or "",
                answer=answer, tool_calls=calls, context=context)


def _rows(path: Path) -> list[tuple[int | str, object]]:
    text = path.read_text(encoding="utf-8")
    rows: list[tuple[int | str, object]] = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append((n, json.loads(line)))
        except json.JSONDecodeError as e:
            if not rows and text.lstrip().startswith(("[", "{")):
                return _json_rows(text)  # one JSON document, pretty-printed
            raise ValueError(f"line {n}: not valid JSON ({e.msg})") from e
    return rows


def _json_rows(text: str) -> list[tuple[int | str, object]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON or JSONL ({e.msg} at line {e.lineno})") from e
    if not isinstance(data, list):
        data = [data]
    return [(f"item {i}", row) for i, row in enumerate(data, 1)]


def load_turns(path: str | Path) -> list[Turn]:
    """Parse a JSONL export (or a JSON list). Raises ValueError naming the bad line."""
    turns: list[Turn] = []
    for n, row in _rows(Path(path)):
        where = f"line {n}" if isinstance(n, int) else str(n)
        if not isinstance(row, dict):
            raise ValueError(f"{where}: expected a JSON object")
        messages = conversation_messages(row)
        if messages is not None:
            conv_id = str(row.get("id", row.get("task_id", n)))
            turns.extend(turns_from_messages(messages, conv_id))
            continue
        try:
            turns.append(parse_row(row, n))
        except ValueError as e:
            raise ValueError(f"{where}: {e}") from e
    return turns
