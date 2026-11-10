"""Score cassandra/faithfulness.py (value check + claim-by-claim judge) on RAGTruth.

Download the two RAGTruth files into poc/ragtruth/data/ first:
  https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/response.jsonl
  https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/source_info.jsonl

Tune on `--split train`; report on `--split test` only once the prompt is frozen.

    python -m poc.ragtruth.run_claims --split train --per-task 50 --out claims_train.jsonl
    python -m poc.ragtruth.run_claims --split test --out claims_test.jsonl

`--per-task N` samples N bad + N good answers per task type (seed 0); omit to run all.
Prints three detectors: value (no LLM), claims (LLM), and either (value OR claims).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import random

from pathlib import Path

from cassandra.faithfulness import claim_check, value_check

HERE = Path(__file__).parent
DATA = HERE / "data"  # response.jsonl + source_info.jsonl from github.com/ParticleMedia/RAGTruth


def _load(models: list[str], split: str) -> list[dict]:
    sources = {}
    for line in (DATA / "source_info.jsonl").open(encoding="utf-8"):
        s = json.loads(line)
        sources[s["source_id"]] = s
    rows = []
    for line in (DATA / "response.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r["split"] == split and r["model"] in models:
            s = sources[r["source_id"]]
            rows.append({"id": r["id"], "model": r["model"], "task": s["task_type"],
                         "truth": bool(r["labels"]), "prompt": s["prompt"],
                         "source": s["source_info"], "response": r["response"]})
    return rows


def _metrics(rows: list[dict]) -> dict:
    tp = sum(r["truth"] and r["flag"] for r in rows)
    fp = sum((not r["truth"]) and r["flag"] for r in rows)
    fn = sum(r["truth"] and not r["flag"] for r in rows)
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return {"n": len(rows), "bad": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": round(p, 3), "recall": round(rc, 3),
            "f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0.0}


def _sample(rows: list[dict], per_task: int) -> list[dict]:
    rng, out = random.Random(0), []
    for task in ("QA", "Summary", "Data2txt"):
        for truth in (True, False):
            pool = [r for r in rows if r["task"] == task and r["truth"] is truth]
            rng.shuffle(pool)
            out += pool[:per_task]
    return out


async def main(a: argparse.Namespace) -> None:
    rows = _load(a.models, a.split)
    if a.per_task:
        rows = _sample(rows, a.per_task)
    out = HERE / a.out
    done = {}
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            v = json.loads(line)
            done[v["id"]] = v
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} responses, {len(todo)} still to check")
    sem, lock = asyncio.Semaphore(a.concurrency), asyncio.Lock()

    async def one(r: dict) -> None:
        async with sem:
            try:
                rep = await claim_check(r["prompt"], r["response"], r["source"])
            except Exception as e:  # retried on the next run
                print(f"  {r['id']}: {type(e).__name__}: {e}")
                return
        rec = {"id": r["id"],
               "unsupported": [c.model_dump() for c in rep.unsupported],
               "n_claims": len(rep.claims)}
        async with lock:
            done[r["id"]] = rec
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    await asyncio.gather(*(one(r) for r in todo))

    results = {}
    for name in ("value", "claims", "either"):
        scored = []
        for r in rows:
            if r["id"] not in done:
                continue
            v = bool(value_check(r["response"], r["source"]))
            c = bool(done[r["id"]]["unsupported"])
            scored.append({**r, "flag": {"value": v, "claims": c, "either": v or c}[name]})
        groups = collections.defaultdict(list)
        for r in scored:
            groups["ALL"].append(r)
            groups[r["task"]].append(r)
        results[name] = {k: _metrics(v) for k, v in groups.items()}
        print(f"--- {name}")
        for k in ("ALL", "QA", "Summary", "Data2txt"):
            if groups[k]:
                m = results[name][k]
                good = m["n"] - m["bad"]
                print(f"  {k:9s} caught {m['tp']}/{m['bad']} ({m['recall']:.0%})  "
                      f"false alarms {m['fp']}/{good} ({m['fp'] / good if good else 0:.1%})  "
                      f"precision {m['precision']:.0%}")
    (HERE / a.out.replace(".jsonl", "_results.json")).write_text(
        json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gpt-4-0613", "gpt-3.5-turbo-0613"])
    ap.add_argument("--split", default="train")
    ap.add_argument("--per-task", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", required=True)
    ap.add_argument("--judge-model", default=None,
                    help="override OPENAI_MODEL (the shell env can't: config loads .env with override)")
    a = ap.parse_args()
    if a.judge_model:
        from cassandra.config import get_settings
        get_settings().openai_model = a.judge_model
    asyncio.run(main(a))
