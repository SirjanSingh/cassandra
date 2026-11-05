"""Auto-postmortem: render a completed Incident as a ready-to-paste markdown report.

Every supervision cycle already produces everything an on-call engineer would
assemble by hand after an AI incident: what happened, how bad it is, why it broke,
the evidence, the proposed fix, and proof the fix works. This module turns that
into one markdown document, written to reports/<incident_id>.md by the pipeline
and returned by the `supervise_latest` MCP tool, so it can be dropped straight
into a GitHub issue, a Slack thread, or a postmortem doc.

Pure function over the Incident model: no LLM calls, no I/O, fully offline-testable.
"""

from __future__ import annotations

from .models import Incident


def render_postmortem(inc: Incident) -> str:
    """Render the incident as markdown. Sections appear as the pipeline filled them."""
    lines: list[str] = []
    title_class = inc.verdict.failure_class.value if inc.verdict else "incident"
    lines.append(f"# Postmortem: {title_class} in production agent ({inc.incident_id})")
    lines.append("")
    lines.append(f"- **Span:** `{inc.span.span_id}` (trace `{inc.span.trace_id}`)")
    lines.append(f"- **Detected:** {inc.created_at.isoformat()}")
    if inc.severity:
        lines.append(f"- **Severity:** {inc.severity.value.upper()}")
    if inc.verdict:
        lines.append(
            f"- **Diagnosis:** {inc.verdict.failure_class.value} "
            f"(confidence {inc.verdict.confidence:.0%})"
        )
    lines.append("")

    lines.append("## What happened")
    lines.append("")
    lines.append(f"**Customer input:**\n\n> {inc.span.input_text}")
    lines.append("")
    lines.append(f"**Agent answer (bad):**\n\n> {inc.span.output_text}")
    if inc.verdict:
        lines.append("")
        lines.append(f"**Why this is a failure:** {inc.verdict.rationale}")
        if inc.verdict.expected_behavior:
            lines.append("")
            lines.append(f"**Expected behavior:** {inc.verdict.expected_behavior}")
    if inc.jury:
        j = inc.jury
        lines.append("")
        requested = j.requested_size or j.size
        lines.append(
            f"**Jury:** {requested} judges requested, {j.size} responded, "
            f"{j.agreement:.0%} agreement (votes: {', '.join(j.votes)})"
            + (" — DEGRADED (jurors errored)" if j.degraded else "")
            + ("" if j.unanimous else " — dissent recorded")
        )
    lines.append("")

    if inc.root_cause:
        rc = inc.root_cause
        lines.append("## Root cause")
        lines.append("")
        lines.append(rc.summary)
        lines.append("")
        lines.append(f"**Culprit:** {rc.culprit}")
        if rc.causal_chain:
            lines.append("")
            lines.append("**Causal chain:**")
            lines.append("")
            for i, step in enumerate(rc.causal_chain, 1):
                lines.append(f"{i}. {step}")
        if rc.contributing_factors:
            lines.append("")
            lines.append("**Contributing factors:** " + "; ".join(rc.contributing_factors))
        lines.append("")
        lines.append(f"**Fix strategy:** {rc.fix_strategy}")
        lines.append("")

    if inc.experiment:
        ex = inc.experiment
        lines.append("## Evaluation")
        lines.append("")
        lines.append(
            f"Synthesized adversarial dataset: {len(inc.dataset_examples)} cases"
            + (f" (Phoenix dataset `{inc.dataset_id}`)" if inc.dataset_id else "")
        )
        lines.append("")
        lines.append("| Prompt | Pass rate |")
        lines.append("|--------|-----------|")
        lines.append(f"| baseline (current) | {ex.baseline_pass_rate:.0%} |")
        if ex.candidate_pass_rate is not None:
            lines.append(f"| candidate (patched) | {ex.candidate_pass_rate:.0%} |")
        if ex.delta is not None:
            lines.append("")
            lines.append(f"**Delta: {ex.delta:+.0%}**")
        eff = inc.efficiency
        if eff and (eff.token_delta_pct is not None or eff.latency_delta_pct is not None):
            lines.append("")
            if eff.token_delta_pct is not None:
                lines.append(f"- Token cost vs baseline: {eff.token_delta_pct:+.0%}")
            if eff.latency_delta_pct is not None:
                lines.append(f"- Latency vs baseline: {eff.latency_delta_pct:+.0%}")
        lines.append("")

    if inc.candidate_prompt:
        lines.append("## Proposed fix (prompt patch)")
        lines.append("")
        if inc.candidate_prompt_version:
            lines.append(f"Registered in Phoenix as prompt version `{inc.candidate_prompt_version}`.")
            lines.append("")
        if inc.prompt_diff:
            lines.append("```diff")
            lines.append(inc.prompt_diff)
            lines.append("```")
        lines.append("")

    if inc.replay:
        rp = inc.replay
        lines.append("## Replay of the original failing input")
        lines.append("")
        lines.append(f"**Verdict: {'FIXED' if rp.fixed else 'STILL BROKEN'}**")
        if rp.judge_rationale:
            lines.append(f" ({rp.judge_rationale})")
        lines.append("")
        lines.append(f"**Before:**\n\n> {rp.before_output}")
        lines.append("")
        lines.append(f"**After:**\n\n> {rp.after_output}")
        lines.append("")

    if inc.redteam:
        rt = inc.redteam
        lines.append("## Red team")
        lines.append("")
        lines.append(
            f"{rt.attacks_run} adversarial probes fired at the live agent: "
            f"{rt.before_pass}/{rt.attacks_run} survived under the current prompt, "
            f"{rt.after_pass}/{rt.attacks_run} under the patch."
        )
        if rt.examples:
            lines.append("")
            lines.append("| Probe | Current | Patched |")
            lines.append("|-------|---------|---------|")
            for row in rt.examples:
                probe = str(row.get("attack", ""))[:80].replace("|", "\\|")
                b = "PASS" if row.get("before_pass") else "FAIL"
                a = "PASS" if row.get("after_pass") else "FAIL"
                lines.append(f"| {probe} | {b} | {a} |")
        lines.append("")

    lines.append("## Next steps")
    lines.append("")
    lines.append("- [ ] Review and approve the candidate prompt version in Phoenix")
    lines.append("- [ ] Add the synthesized dataset to the CI prompt gate")
    lines.append("- [ ] Deploy the patched prompt and watch the next supervision cycles")
    lines.append("")
    lines.append("*Generated automatically by Cassandra, the meta-agent that watches other agents.*")
    return "\n".join(lines)
