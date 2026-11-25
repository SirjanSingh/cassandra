"""Measure the action check on tau-bench's published trajectories. No LLM, no API key.

Data: sierra-research/tau-bench `historical_trajectories/` (not committed). Download:

    mkdir -p data/tau && cd data/tau
    for f in gpt-4o-airline gpt-4o-retail sonnet-35-new-airline sonnet-35-new-retail; do
      curl -sLO "https://raw.githubusercontent.com/sierra-research/tau-bench/main/historical_trajectories/$f.json"
    done
    cd - && python -m poc.taubench.run_action_check data/tau

Each trajectory carries a programmatic `reward` computed from the environment's final
database state, independent of the agent's text: reward < 1 means the task failed. A
trajectory counts as flagged when any of its turns gets an action-check finding. The
importer, engine and check used are the shipped ones (`cassandra_ai.scan.load_turns`,
`cassandra_ai.engine.check_offline`).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from cassandra_ai.engine import check_offline
from cassandra_ai.importers import turns_from_messages


def main(data_dir: Path, out: Path | None) -> None:
    rows = []
    for f in sorted(data_dir.glob("*.json")):
        for t in json.loads(f.read_text(encoding="utf-8")):
            turns = turns_from_messages(t["traj"], f"{f.stem}/{t['task_id']}/{t.get('trial', 0)}")
            hits = [(r.turn.id, fd.claim, fd.detail) for tr in turns
                    for r in [check_offline(tr)] for fd in r.findings if fd.layer == "action"]
            rows.append({"file": f.stem, "failed": t["reward"] < 1.0, "turns": len(turns),
                         "flagged": bool(hits), "hits": hits})

    n = len(rows)
    failed = [r for r in rows if r["failed"]]
    passed = [r for r in rows if not r["failed"]]
    tp = sum(r["flagged"] for r in failed)
    fp = sum(r["flagged"] for r in passed)
    summary = {
        "trajectories": n,
        "turns_checked": sum(r["turns"] for r in rows),
        "failed": len(failed),
        "base_rate": round(len(failed) / n, 4),
        "flagged_failed": tp,
        "flagged_passed": fp,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / len(failed), 4),
        "per_file": {k: {"flagged_failed": sum(r["flagged"] for r in failed if r["file"] == k),
                         "flagged_passed": sum(r["flagged"] for r in passed if r["file"] == k)}
                     for k in sorted(Counter(r["file"] for r in rows))},
    }
    print(json.dumps(summary, indent=2))
    if out:
        out.write_text(json.dumps({"summary": summary,
                                   "flagged": [r for r in rows if r["flagged"]]}, indent=1),
                       encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
