"""Turn a scan into something a bot owner reads: self-contained HTML, Markdown, or JSON."""

from __future__ import annotations

import html
import json
from datetime import date

from .models import Finding, Report, TurnResult, Verdict

_LAYER_NAMES = {"rule": "tool-call rule", "value": "number & time check",
                "claim": "claim-by-claim check"}
_KIND_TEXT = {
    "no_tool_call": "No tool call backs this",
    "tool_returned_empty": "Tool returned this empty",
    "value_not_in_data": "Not in the data",
    "contradicted": "Contradicts the data",
    "not_in_source": "Not in the data",
}


_ROWS: tuple[tuple[str, Verdict], ...] = (
    ("Flagged", "flagged"), ("Backed by its data", "ok"),
    ("Declined to answer", "declined"), ("No data to check", "unchecked"))


def _pct(n: int, total: int) -> str:
    return f"{round(100 * n / total)}%" if total else "0%"


def _clip(text: str, limit: int = 500) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _offline_note(report: Report) -> str | None:
    if "claim" in report.layers:
        return None
    return ("Only the free offline checks ran (tool-call rule and numbers/times). The "
            "claim-by-claim check found about 5x more bad answers on a public benchmark; "
            "rerun with --llm to include it.")


def summary_line(report: Report) -> str:
    total, flagged = len(report.results), report.count("flagged")
    return (f"{flagged} of {total} answers ({_pct(flagged, total)}) stated something the "
            f"bot's own data does not back ({report.count('unchecked')} had no data to check).")


# ----------------------------------------------------------------------------- markdown

def _md_finding(f: Finding) -> str:
    detail = f" — {_clip(f.detail, 200)}" if f.detail else ""
    return f"- **{_KIND_TEXT[f.kind]}** ({_LAYER_NAMES[f.layer]}): `{_clip(f.claim, 160)}`{detail}"


def render_markdown(report: Report, top: int = 20) -> str:
    total = len(report.results)
    flagged = [r for r in report.results if r.verdict == "flagged"]
    lines = [
        "# Cassandra answer check", "",
        f"Source: `{report.source}` · {total} answers · {date.today().isoformat()} · "
        f"checks: {', '.join(_LAYER_NAMES[x] for x in report.layers)}"
        + (f" · model: {report.model}" if report.model else ""), "",
        f"**{summary_line(report)}**", "",
        "| Result | Answers | Share |", "|---|---|---|",
    ]
    for label, v in _ROWS:
        lines.append(f"| {label} | {report.count(v)} | {_pct(report.count(v), total)} |")
    lines.append("")
    if note := _offline_note(report):
        lines += [f"> {note}", ""]
    if flagged:
        lines += [f"## Flagged answers ({min(top, len(flagged))} of {len(flagged)})", ""]
        for i, r in enumerate(flagged[:top], 1):
            t = r.turn
            lines += [f"### {i}. `{t.id}` — {_clip(t.question, 140) or '(no question)'}", "",
                      f"> {_clip(t.answer)}", ""]
            lines += [_md_finding(f) for f in r.findings] + [""]
    lines += ["## How to read this", "",
              "- *Flagged* means at least one statement isn't backed by the tool results or "
              "documents logged for that turn. Review it; it is unverified, not proven false.",
              "- The checks only see what was logged. If the bot used data you didn't export, "
              "its answers will look unbacked.", ""]
    return "\n".join(lines)


# ----------------------------------------------------------------------------- html

_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--line:#e4e1d8;--card:#fff;--bad:#b42318;
--badbg:#fdecea;--ok:#1f7a4d;--okbg:#e7f4ec;--warn:#8a5a00;--warnbg:#fff4dc}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--fg:#ecebe6;--muted:#a3a29b;
--line:#33322e;--card:#1f1f1c;--bad:#ff8a80;--badbg:#3a1d1a;--ok:#7fd1a5;--okbg:#16301f;
--warn:#f5c26b;--warnbg:#33280f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:920px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:36px 0 12px}
.meta{color:var(--muted);font-size:13px}.lead{font-size:18px;margin:20px 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile b{display:block;font-size:24px}.tile span{color:var(--muted);font-size:13px}
.tile.bad b{color:var(--bad)}.note{background:var(--warnbg);color:var(--warn);
border-radius:10px;padding:12px 14px;margin:16px 0}
.turn{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px 16px;margin:12px 0}.q{font-weight:600}.a{border-left:3px solid var(--line);
padding-left:10px;margin:8px 0;color:var(--muted);white-space:pre-wrap}
.f{margin:8px 0 0}.badge{display:inline-block;font-size:12px;font-weight:600;
border-radius:999px;padding:1px 9px;background:var(--badbg);color:var(--bad);margin-right:6px}
.layer{color:var(--muted);font-size:12px}.claim{font-weight:600}
.detail{color:var(--muted);font-size:13px;margin-top:2px}code{font-size:13px}
ul{padding-left:20px}footer{color:var(--muted);font-size:12px;margin-top:40px}
"""


def _e(x: object) -> str:
    return html.escape(str(x), quote=True)


def _html_turn(i: int, r: TurnResult) -> str:
    t = r.turn
    fs = "".join(
        f'<div class="f"><span class="badge">{_e(_KIND_TEXT[f.kind])}</span>'
        f'<span class="claim">{_e(_clip(f.claim, 200))}</span> '
        f'<span class="layer">· {_e(_LAYER_NAMES[f.layer])}</span>'
        + (f'<div class="detail">{_e(_clip(f.detail, 300))}</div>' if f.detail else "")
        + "</div>"
        for f in r.findings)
    return (f'<div class="turn"><div class="meta">#{i} · {_e(t.id)}</div>'
            f'<div class="q">{_e(_clip(t.question, 300) or "(no question logged)")}</div>'
            f'<div class="a">{_e(_clip(t.answer, 1200))}</div>{fs}</div>')


def render_html(report: Report, top: int = 50) -> str:
    total = len(report.results)
    flagged = [r for r in report.results if r.verdict == "flagged"]
    tiles = "".join(
        f'<div class="tile{" bad" if v == "flagged" else ""}"><b>{report.count(v)}</b>'
        f"<span>{label} · {_pct(report.count(v), total)}</span></div>"
        for label, v in _ROWS)
    note = _offline_note(report)
    checks = ", ".join(_LAYER_NAMES[x] for x in report.layers) or "none"
    body = [
        "<main>",
        "<h1>Cassandra answer check</h1>",
        f'<div class="meta">{_e(report.source)} · {total} answers · {date.today().isoformat()}'
        f" · checks: {_e(checks)}" + (f" · model: {_e(report.model)}" if report.model else "")
        + "</div>",
        f'<p class="lead">{_e(summary_line(report))}</p>',
        f'<div class="tiles">{tiles}</div>',
        f'<div class="note">{_e(note)}</div>' if note else "",
    ]
    if flagged:
        body.append(f"<h2>Flagged answers ({min(top, len(flagged))} of {len(flagged)})</h2>")
        body += [_html_turn(i, r) for i, r in enumerate(flagged[:top], 1)]
    else:
        body.append("<h2>No flagged answers</h2><p>Every checked answer was backed by its data."
                    "</p>")
    body += [
        "<h2>How to read this</h2><ul>",
        "<li><b>Flagged</b> means at least one statement isn't backed by the tool results or "
        "documents logged for that turn. It is unverified, not proven false: review it.</li>",
        "<li>The checks only see what was logged. If the bot used data you didn't export, its "
        "answers will look unbacked.</li>",
        "<li>On a public human-labelled benchmark (RAGTruth), the claim check caught 43% of "
        "bad answers, and about 1 in 4 of its flags were real problems. Treat this as a "
        "review queue, not a final verdict.</li></ul>",
        "<footer>Generated by Cassandra · checks bot answers against the bot's own data · "
        "github.com/SirjanSingh/cassandra</footer>",
        "</main>",
    ]
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>Cassandra answer check</title><style>{_CSS}</style></head><body>"
            + "".join(body) + "</body></html>")


def render_json(report: Report) -> str:
    return json.dumps(report.model_dump(mode="json"), indent=1, ensure_ascii=False)
