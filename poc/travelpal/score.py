"""Score Cassandra's verdicts on the real TravelPal runs against the hand labels.

Three detectors, each the real Cassandra code path:
  * rule    — Layer 1 deterministic grounding (cassandra/grounding.py) with
              poc/travelpal/grounding_spec.json; abstains when it can't decide.
  * judge   — Diagnostician.judge, the LLM-as-judge used on production spans.
  * cascade — what the oracle does: rule first, LLM judge only where the rule abstains.

    python -m poc.travelpal.score [--runs runs.jsonl --labels labels.json --out results.json]
Prints the confusion matrices and writes the per-turn verdicts to --out.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from cassandra.diagnostician import Diagnostician
from cassandra.grounding import GroundingSpec, check_grounding
from cassandra.models import FailureClass

HERE = Path(__file__).parent


def _metrics(rows: list[dict], key: str) -> dict:
    tp = sum(r["truth"] and r[key] for r in rows)
    fp = sum((not r["truth"]) and r[key] for r in rows)
    fn = sum(r["truth"] and not r[key] for r in rows)
    tn = len(rows) - tp - fp - fn
    return {
        "n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
    }


async def main(runs_file: str, labels_file: str, out_file: str) -> None:
    runs = [json.loads(line) for line in (HERE / runs_file).read_text(encoding="utf-8").splitlines()]
    labels = json.loads((HERE / labels_file).read_text(encoding="utf-8"))["bad"]
    spec = GroundingSpec.model_validate_json((HERE / "grounding_spec.json").read_text(encoding="utf-8"))
    diag = Diagnostician()
    sem = asyncio.Semaphore(6)

    async def judge(r: dict):
        async with sem:
            return await diag.judge(r["question"], r["reply"], r["tool_calls"])

    verdicts = await asyncio.gather(*(judge(r) for r in runs))

    rows = []
    for r, v in zip(runs, verdicts):
        g = check_grounding(r["reply"], r["tool_calls"], spec)
        rule = None if g.abstain else g.failure_class is not FailureClass.OK
        judge_bad = v.failure_class is not FailureClass.OK
        rows.append({
            "id": r["id"], "category": r["category"],
            "truth": r["id"] in labels, "truth_type": labels.get(r["id"], [None])[0],
            "rule": rule, "rule_why": g.rationale,
            "judge": judge_bad, "judge_class": v.failure_class.value, "judge_why": v.rationale,
            "cascade": judge_bad if rule is None else rule,
            "cascade_layer": "llm" if rule is None else "rule",
        })

    decided = [r for r in rows if r["rule"] is not None]
    summary = {
        "truth_bad": sum(r["truth"] for r in rows),
        "cascade_flagged": sum(r["cascade"] for r in rows),
        "rule_coverage": f"{len(decided)}/{len(rows)}",
        "rule_on_decided": _metrics(decided, "rule"),
        "judge": _metrics(rows, "judge"),
        "cascade": _metrics(rows, "cascade"),
    }
    (HERE / out_file).write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=1))
    for r in rows:
        if r["truth"] != r["cascade"] or r["truth"] != r["judge"]:
            print(f'{r["id"]} truth={r["truth"]} ({r["truth_type"]}) rule={r["rule"]} '
                  f'judge={r["judge"]}[{r["judge_class"]}] cascade={r["cascade"]}\n'
                  f'   rule: {r["rule_why"][:140]}\n   judge: {r["judge_why"][:160]}')


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs.jsonl")
    ap.add_argument("--labels", default="labels.json")
    ap.add_argument("--out", default="results.json")
    a = ap.parse_args()
    asyncio.run(main(a.runs, a.labels, a.out))
