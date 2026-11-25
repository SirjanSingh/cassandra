"""Read a bot's exported chat logs (JSONL, one turn per line) into `Turn`s.

    {"id": "t1", "question": "...", "answer": "...",
     "tool_calls": [{"name": "...", "args": {...}, "result": {...}}],
     "context": "retrieved text, a list of passages, or a JSON object"}

Aliases accepted: question = input / user / message; answer = output / reply / response;
tool_calls = tools; context = documents / retrieved / sources.
"""

from __future__ import annotations

import json
from pathlib import Path

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


def load_turns(path: str | Path) -> list[Turn]:
    """Parse a JSONL export. Raises ValueError naming the bad line."""
    turns: list[Turn] = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"line {n}: not valid JSON ({e.msg})") from e
        if not isinstance(row, dict):
            raise ValueError(f"line {n}: expected a JSON object")
        try:
            turns.append(parse_row(row, n))
        except ValueError as e:
            raise ValueError(f"line {n}: {e}") from e
    return turns
