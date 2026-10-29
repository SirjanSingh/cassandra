"""`cassandra scan` — which answers in exported chat logs stated facts no tool backed?

The smallest way to try Cassandra on someone else's agent: no Phoenix, no replay
endpoint, no code change on their side. Input is a JSONL export, one turn per line:

    {"id": "t1", "question": "...", "answer": "...", "tool_calls": [{"name", "args", "result"}]}

(`input`/`user`/`message` and `output`/`reply`/`response` are accepted as aliases.)

Each turn goes through the deterministic grounding rule (cassandra/grounding.py) with the
agent's GroundingSpec. Rule-only is the default — no LLM call, the logs never leave the
machine. With `judge=True`, only the turns the rule can't decide go to the LLM judge
(Diagnostician.judge), mirroring the oracle cascade.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .grounding import GroundingSpec, _extract_claims, check_grounding
from .models import FailureClass

Status = Literal["unsupported", "ok", "declined", "undecided"]

_QUESTION_KEYS = ("question", "input", "user", "message")
_ANSWER_KEYS = ("answer", "output", "reply", "response")


class Turn(BaseModel):
    id: str
    question: str = ""
    answer: str
    tool_calls: list[dict] = Field(default_factory=list)


class TurnResult(BaseModel):
    turn: Turn
    status: Status
    claim: str = ""
    rationale: str = ""
    layer: Literal["rule", "llm"] = "rule"


class ScanReport(BaseModel):
    source: str
    mode: str
    results: list[TurnResult]

    def count(self, status: Status) -> int:
        return sum(r.status == status for r in self.results)


def _first(row: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        if isinstance(row.get(k), str):
            return row[k]
    return None


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
        answer = _first(row, _ANSWER_KEYS)
        if answer is None:
            raise ValueError(f"line {n}: no answer field (expected one of {', '.join(_ANSWER_KEYS)})")
        calls = row.get("tool_calls", row.get("tools"))
        if calls is None:
            calls = []
        if not isinstance(calls, list):
            raise ValueError(f"line {n}: tool_calls must be a list")
        turns.append(Turn(
            id=str(row.get("id", n)), question=_first(row, _QUESTION_KEYS) or "",
            answer=answer, tool_calls=calls,
        ))
    return turns


def check_turn(turn: Turn, spec: GroundingSpec) -> TurnResult:
    """Rule-only verdict for one turn (pure: no LLM, no network)."""
    v = check_grounding(turn.answer, turn.tool_calls, spec)
    if v.abstain:
        return TurnResult(turn=turn, status="undecided", claim=v.claim, rationale=v.rationale)
    if v.failure_class is FailureClass.OK:
        status: Status = "ok" if _extract_claims(turn.answer, spec) else "declined"
        return TurnResult(turn=turn, status=status, claim=v.claim, rationale=v.rationale)
    return TurnResult(turn=turn, status="unsupported", claim=v.claim, rationale=v.rationale)


async def scan(turns: list[Turn], spec: GroundingSpec, *, judge: bool = False) -> list[TurnResult]:
    """Rule on every turn; with `judge`, the LLM decides only the rule's undecided turns."""
    results = [check_turn(t, spec) for t in turns]
    if not judge:
        return results
    from .diagnostician import Diagnostician

    diag = Diagnostician()
    for r in results:
        if r.status != "undecided":
            continue
        t = r.turn
        v = await diag.judge(t.question, t.answer, t.tool_calls)
        r.status = "unsupported" if v.is_failure else "ok"
        r.rationale, r.layer = v.rationale, "llm"
    return results


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


def _clip(text: str, limit: int = 400) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_markdown(report: ScanReport, top: int = 10) -> str:
    """The one-page report a bot owner reads."""
    res = report.results
    total = len(res)
    bad = [r for r in res if r.status == "unsupported"]
    undecided = [r for r in res if r.status == "undecided"]
    lines = [
        "# Cassandra scan report",
        "",
        f"Source: `{report.source}` · {total} answers · {date.today().isoformat()} · {report.mode}",
        "",
        f"**{len(bad)} of {total} answers ({_pct(len(bad), total)}) stated a specific fact "
        "that no tool call backed.**",
        "",
        "| Result | Answers | Share |",
        "|---|---|---|",
        f"| Unsupported fact | {len(bad)} | {_pct(len(bad), total)} |",
        f"| Backed by a tool result | {report.count('ok')} | {_pct(report.count('ok'), total)} |",
        f"| Honest decline | {report.count('declined')} | {_pct(report.count('declined'), total)} |",
        f"| Not checkable | {len(undecided)} | {_pct(len(undecided), total)} |",
        "",
    ]
    if bad:
        lines += [f"## Examples ({min(top, len(bad))} of {len(bad)})", ""]
        for i, r in enumerate(bad[:top], 1):
            t = r.turn
            lines += [f"### {i}. `{t.id}` — {_clip(t.question, 120) or '(no question)'}", "",
                      f"> {_clip(t.answer)}", ""]
            if r.claim and r.layer == "rule":
                lines.append(f"- Claim: `{_clip(r.claim, 80)}`")
            lines += [f"- Why: {r.rationale}" + (" *(LLM judge)*" if r.layer == "llm" else ""), ""]
    if undecided:
        ids = ", ".join(f"`{r.turn.id}`" for r in undecided[:20])
        more = f" and {len(undecided) - 20} more" if len(undecided) > 20 else ""
        lines += [
            "## Not checkable",
            "",
            f"{len(undecided)} answers made no claim the grounding spec recognises: {ids}{more}.",
            "Add a `claim_extractors` pattern for them, or rerun with `--judge` to let the LLM "
            "judge decide these only.",
            "",
        ]
    lines += [
        "## How to read this",
        "",
        "- *Unsupported* means the answer states a specific fact (amount, date, place…) and no "
        "successful tool call in that turn backs it. It is unverified, not necessarily false.",
        "- The rule checks that a matching tool call succeeded, not that it answered the right "
        "question: a tool result for the wrong city or the wrong date still counts as backed.",
        "",
    ]
    return "\n".join(lines)
