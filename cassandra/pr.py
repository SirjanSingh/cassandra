"""Open the proven prompt fix as a pull request (the "ship it" surface).

Every supervision cycle already produces a candidate prompt, a unified diff, before/
after replay evidence, and a paste-ready postmortem. This module turns that into a
GitHub pull request: branch → write the new prompt to the agent's prompt file →
commit → push → `gh pr create`, with the postmortem as the PR body and the pass-rate
delta as the headline. Cassandra stops being a dashboard and becomes a teammate who
opens the fix for human review.

Design guardrails (this is an OUTWARD-FACING, hard-to-reverse action):
  * It is **never** wired into the autonomous pipeline — it is only invoked explicitly
    (`cassandra pr <id>`), so an AI never edits a prompt + opens a PR unsupervised.
  * `dry_run` (the default for previews) touches nothing; it returns the exact branch,
    title, and body that WOULD be opened.
  * Local git mutation (branch + commit) and the outward push/`gh pr create` are
    separate gates: `push=False` prepares the branch locally and prints the command;
    `push=True` is the only path that talks to GitHub.

`build_pr_content` and `load_incident` are pure/offline (fully unit-tested); only
`open_pr` shells out to git/gh.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel

from .config import get_settings
from .models import Incident
from .report import render_postmortem


class PRContent(BaseModel):
    """Everything needed to open (or preview) the PR — no side effects to produce it."""

    title: str
    branch: str
    body: str


class PRResult(BaseModel):
    """What `open_pr` actually did."""

    opened: bool = False  # a PR was created on GitHub
    committed: bool = False  # a local branch + commit was made
    dry_run: bool = False
    branch: str
    title: str
    prompt_file: str | None = None
    pr_url: str | None = None
    detail: str = ""


def load_incident(incident_id: str, reports_dir: str | Path = "reports") -> Incident:
    """Reconstruct a completed Incident from reports/<incident_id>.json."""
    path = Path(reports_dir) / f"{incident_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"No serialized incident at {path}. Run a supervision cycle first "
            f"(`cassandra run`) — it writes reports/<id>.json."
        )
    return Incident.model_validate_json(path.read_text(encoding="utf-8"))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", text.lower()).strip("-")[:60] or "incident"


def build_pr_content(inc: Incident) -> PRContent:
    """Pure: derive the PR branch/title/body from a completed incident."""
    fclass = inc.verdict.failure_class.value if inc.verdict else "failure"
    title = f"fix(prompt): harden agent against {fclass} [{inc.incident_id}]"
    branch = f"cassandra/fix-{_slug(inc.incident_id)}"

    header = ["> 🤖 Opened by **Cassandra**, the meta-agent that watches other agents.", ""]
    if inc.experiment and inc.experiment.delta is not None:
        header.append(
            f"**Pass rate: {inc.experiment.baseline_pass_rate:.0%} → "
            f"{inc.experiment.candidate_pass_rate:.0%} "
            f"({inc.experiment.delta:+.0%})** on the synthesized regression suite."
        )
    if inc.replay:
        header.append(
            f"**Replay of the original failing input: "
            f"{'FIXED' if inc.replay.fixed else 'STILL BROKEN'}.**"
        )
    header.append("")
    body = "\n".join(header) + render_postmortem(inc)
    return PRContent(title=title, branch=branch, body=body)


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def open_pr(
    inc: Incident,
    *,
    prompt_file: str | None = None,
    base: str = "main",
    branch: str | None = None,
    dry_run: bool = False,
    push: bool = False,
) -> PRResult:
    """Prepare (and optionally push) the fix PR.

    `dry_run=True` returns the plan without touching anything. Otherwise a local branch
    + commit is made against `prompt_file` (falls back to BASELINE_PROMPT_FILE); the
    outward push + `gh pr create` happens only when `push=True`.
    """
    content = build_pr_content(inc)
    branch = branch or content.branch
    result = PRResult(branch=branch, title=content.title, dry_run=dry_run)

    if dry_run:
        result.detail = "dry run — nothing was changed. Body:\n\n" + content.body
        return result

    if inc.candidate_prompt is None:
        raise ValueError(
            f"Incident {inc.incident_id} has no candidate prompt to commit "
            "(the patch stage never ran)."
        )
    target = prompt_file or get_settings().baseline_prompt_file
    if not target:
        raise ValueError(
            "No prompt file to patch. Pass --prompt-file PATH (or set "
            "BASELINE_PROMPT_FILE) pointing at your agent's system-prompt file so the "
            "candidate prompt can be committed."
        )
    if shutil.which("git") is None:
        raise RuntimeError("git not found on PATH.")

    if _run(["git", "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        raise RuntimeError("Not inside a git repository.")

    # Branch (reuse if it already exists), then write + commit the new prompt.
    if _run(["git", "switch", "-c", branch]).returncode != 0:
        _run(["git", "switch", branch])
    Path(target).write_text(inc.candidate_prompt, encoding="utf-8")
    _run(["git", "add", target])
    commit = _run(["git", "commit", "-m", content.title])
    if commit.returncode != 0:
        raise RuntimeError(f"git commit failed: {commit.stderr.strip() or commit.stdout.strip()}")
    result.committed = True
    result.prompt_file = target

    if not push:
        result.detail = (
            f"Committed the patched prompt on branch '{branch}'. To open the PR:\n"
            f"  git push -u origin {branch}\n"
            f"  gh pr create --base {base} --head {branch} "
            f"--title {content.title!r} --body-file <postmortem>\n"
            "Or re-run with --push to do this automatically."
        )
        return result

    if shutil.which("gh") is None:
        raise RuntimeError("gh (GitHub CLI) not found on PATH; cannot open the PR.")
    if _run(["git", "push", "-u", "origin", branch]).returncode != 0:
        raise RuntimeError(f"git push failed for branch '{branch}'.")

    # Body via a temp file so multiline markdown survives argv.
    body_path = Path("reports") / f"{inc.incident_id}.prbody.md"
    body_path.write_text(content.body, encoding="utf-8")
    created = _run(
        ["gh", "pr", "create", "--base", base, "--head", branch,
         "--title", content.title, "--body-file", str(body_path)]
    )
    if created.returncode != 0:
        raise RuntimeError(f"gh pr create failed: {created.stderr.strip()}")
    result.opened = True
    result.pr_url = created.stdout.strip()
    result.detail = f"Opened PR: {result.pr_url}"
    return result
