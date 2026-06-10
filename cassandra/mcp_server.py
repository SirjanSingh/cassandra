"""`cassandra-mcp` — Cassandra's OWN MCP server (the meta-agent, published as tools).

Cassandra *consumes* the Arize Phoenix MCP (see phoenix_mcp.py); this module turns it
around and *publishes* Cassandra's supervision capabilities as MCP tools, so any other
agent or IDE (Claude Desktop, Cursor, …) can call them:

    diagnose          - LLM-as-judge verdict on one agent turn (raw text, no Phoenix)
    synthesize_evals  - turn a failure into an adversarial eval set (raw text)
    propose_patch     - rewrite a system prompt to close a failure, with a unified diff
    gate_prompt       - CI regression gate: score a prompt vs eval cases, pass/block
    supervise_latest  - run the FULL Phoenix-deep loop on the latest production trace
                        (diagnose -> root-cause -> synthesize -> evaluate -> patch ->
                         replay -> red-team), writing annotations/datasets/prompts back
                         into Phoenix via the partner MCP

    self_evaluate     - grade Cassandra's own diagnostic accuracy vs ground truth

The composable tools are provider-agnostic (no Phoenix required); supervise_latest is
the headline tool that exercises the whole partner-MCP surface and now also returns a
paste-ready markdown postmortem. See docs/WORKFLOWS.md for end-to-end recipes (live
supervision, CI gating, IDE copilot, on-call postmortems).

Run it:  cassandra-mcp           (stdio)  — or  python -m cassandra.mcp_server
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from . import llm
from .diagnostician import Diagnostician
from .models import Incident
from .patcher import _SYSTEM as _PATCH_SYS, _Patch
from .synthesizer import _SYSTEM as _SYNTH_SYS, _Batch

mcp = FastMCP("cassandra")


# --- composable, provider-agnostic tools (no Phoenix needed) -------------------


@mcp.tool()
async def diagnose(
    customer_input: str, agent_output: str, tool_calls: str = ""
) -> dict:
    """Judge a single agent turn for hallucination / prompt-drift / tool-failure.

    Returns {failure_class, confidence, rationale, expected_behavior, is_failure}.
    """
    v = await Diagnostician().judge(customer_input, agent_output, tool_calls)
    return {**v.model_dump(), "is_failure": v.is_failure}


@mcp.tool()
async def synthesize_evals(
    failure_class: str,
    why_it_failed: str,
    original_input: str,
    bad_output: str,
    n: int = 8,
) -> list[dict]:
    """Generate `n` adversarial eval probes that stress the same weakness.

    Each probe is {input_text, expected_answer, acceptance_criterion}.
    """
    prompt = (
        f"FAILURE CLASS: {failure_class}\n"
        f"WHY IT FAILED: {why_it_failed}\n"
        f"ORIGINAL INPUT: {original_input}\n"
        f"BAD OUTPUT: {bad_output}\n\n"
        f"Generate exactly {n} diverse adversarial probes as JSON."
    )
    batch: _Batch = await llm.structured(prompt, _Batch, system=_SYNTH_SYS)
    return [e.model_dump() for e in batch.examples[:n]]


@mcp.tool()
async def propose_patch(
    current_prompt: str,
    failure_summary: str,
    triggering_input: str,
    bad_output: str,
) -> dict:
    """Rewrite a system prompt so it can no longer commit the observed failure.

    Returns {revised_prompt, change_summary, diff} (unified diff vs current_prompt).
    """
    import difflib

    prompt = (
        f"CURRENT SYSTEM PROMPT:\n{current_prompt}\n\n"
        f"OBSERVED FAILURE: {failure_summary}\n"
        f"TRIGGERING INPUT: {triggering_input}\n"
        f"BAD OUTPUT: {bad_output}\n\n"
        "Make the minimal, surgical change. Return the revised prompt JSON."
    )
    patch: _Patch = await llm.structured(prompt, _Patch, system=_PATCH_SYS)
    diff = "\n".join(
        difflib.unified_diff(
            current_prompt.splitlines(),
            patch.revised_prompt.splitlines(),
            fromfile="current",
            tofile="candidate",
            lineterm="",
        )
    )
    return {
        "revised_prompt": patch.revised_prompt,
        "change_summary": patch.change_summary,
        "diff": diff,
    }


@mcp.tool()
async def gate_prompt(prompt: str, cases: list[dict], threshold: float = 0.8) -> dict:
    """CI regression gate: score a system prompt against eval cases on the live agent.

    Each case is {input_text, expected_answer, acceptance_criterion} (the same shape
    `synthesize_evals` emits, so synthesized datasets become regression suites).
    Returns {total, passed_cases, pass_rate, threshold, passed, cases}; `passed` is
    false when pass_rate < threshold, i.e. the prompt change should be blocked.
    The same check ships as the `cassandra-gate` CLI for GitHub Actions.
    """
    from .gate import run_gate
    from .models import DatasetExample

    parsed = [DatasetExample.model_validate(c) for c in cases]
    res = await run_gate(prompt, parsed, threshold=threshold)
    return res.model_dump()


# --- headline tool: the full Phoenix-deep supervision loop ---------------------


@mcp.tool()
async def supervise_latest() -> dict:
    """Run Cassandra's full supervision loop on the latest production trace.

    Polls the configured Phoenix project (PATIENT_PROJECT), and on the first fresh
    failing span runs diagnose -> root-cause -> synthesize -> evaluate(baseline) ->
    patch -> evaluate(candidate) -> replay -> red-team, writing annotations, the
    eval dataset, and the candidate prompt version back into Phoenix.

    Returns a structured incident report, or {handled: false} if nothing failing
    was found this cycle.
    """
    # Imported lazily: pulls in the live pipeline (Phoenix MCP + Patient endpoint).
    from .loop_agent import SupervisionPipeline

    inc = await SupervisionPipeline().run_once()
    if inc is None:
        return {"handled": False, "reason": "no fresh failing spans"}
    from .report import render_postmortem

    # `postmortem` is paste-ready markdown (GitHub issue / Slack); also written
    # to reports/<incident_id>.md by the pipeline itself.
    return {"handled": True, **_report(inc), "postmortem": render_postmortem(inc)}


@mcp.tool()
async def self_evaluate() -> dict:
    """Grade Cassandra's OWN diagnostic accuracy against a labeled ground-truth set.

    Runs the trap library through the live Patient + Cassandra's Diagnostician and
    scores the verdicts vs ground truth. Returns {total, correct, accuracy, per_class}.
    This is the introspection loop: the meta-agent measuring how well it supervises.
    """
    from .selfeval import SelfEvaluator

    card = await SelfEvaluator().evaluate()
    return {
        "total": card.total,
        "correct": card.correct,
        "accuracy": card.accuracy,
        "per_class": card.per_class,
    }


def _report(inc: Incident) -> dict[str, Any]:
    r: dict[str, Any] = {
        "incident_id": inc.incident_id,
        "span_id": inc.span.span_id,
        "stage": inc.stage.value,
        "dataset_size": len(inc.dataset_examples),
    }
    if inc.verdict:
        r["verdict"] = {
            "failure_class": inc.verdict.failure_class.value,
            "confidence": inc.verdict.confidence,
            "rationale": inc.verdict.rationale,
        }
    if inc.severity:
        r["severity"] = inc.severity.value
    if inc.efficiency:
        r["efficiency"] = {
            "token_delta_pct": inc.efficiency.token_delta_pct,
            "latency_delta_pct": inc.efficiency.latency_delta_pct,
        }
    if inc.root_cause:
        r["root_cause"] = {
            "culprit": inc.root_cause.culprit,
            "summary": inc.root_cause.summary,
            "fix_strategy": inc.root_cause.fix_strategy,
        }
    if inc.experiment:
        r["evaluation"] = {
            "baseline_pass_rate": inc.experiment.baseline_pass_rate,
            "candidate_pass_rate": inc.experiment.candidate_pass_rate,
            "delta": inc.experiment.delta,
        }
    if inc.candidate_prompt:
        r["patch"] = {
            "candidate_prompt_version": inc.candidate_prompt_version,
            "diff": inc.prompt_diff,
        }
    if inc.replay:
        r["replay"] = {
            "fixed": inc.replay.fixed,
            "before": inc.replay.before_output,
            "after": inc.replay.after_output,
        }
    if inc.redteam:
        r["red_team"] = {
            "attacks_run": inc.redteam.attacks_run,
            "before_pass": inc.redteam.before_pass,
            "after_pass": inc.redteam.after_pass,
        }
    return r


def main() -> None:
    """Console entry point (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
