"""Grade Cassandra's LLM judge against RAGTruth's human hallucination labels.

RAGTruth (ParticleMedia, ACL 2024): ~18k answers from six LLMs on RAG tasks (QA over
retrieved passages, news summary, data-to-text from business JSON), each annotated by
humans for spans the source does not support. Download into poc/ragtruth/data/:
  https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/response.jsonl
  https://raw.githubusercontent.com/ParticleMedia/RAGTruth/main/dataset/source_info.jsonl

The judge is used UNCHANGED (Diagnostician.judge). The retrieved source is passed the way a
RAG bot exposes it: as the result of a `retrieve_documents` tool call. A response counts as
flagged when the verdict is anything other than `ok`.

    python -m poc.ragtruth.run_judge [--models gpt-4-0613 gpt-3.5-turbo-0613] [--split test]

Writes per-response verdicts to poc/ragtruth/verdicts.jsonl (resumable) and prints metrics.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
from pathlib import Path

from cassandra_ai.diagnostician import Diagnostician
from cassandra_ai.models import FailureClass

HERE = Path(__file__).parent
DATA = HERE / "data"


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
            rows.append({
                "id": r["id"], "model": r["model"], "task": s["task_type"],
                "truth": bool(r["labels"]), "prompt": s["prompt"],
                "source": s["source_info"], "response": r["response"],
            })
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


async def main(models: list[str], split: str, concurrency: int, out: str, sample: int) -> None:
    OUT = HERE / out
    rows = _load(models, split)
    if sample:  # every bad answer + a fixed random slice of good ones (precision then skewed)
        import random
        good = [r for r in rows if not r["truth"]]
        random.Random(0).shuffle(good)
        rows = [r for r in rows if r["truth"]] + good[: max(0, sample - sum(r["truth"] for r in rows))]
    done = {}
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            v = json.loads(line)
            done[v["id"]] = v
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} responses, {len(todo)} still to judge")

    judge, sem, lock = Diagnostician(), asyncio.Semaphore(concurrency), asyncio.Lock()

    async def one(r: dict) -> None:
        async with sem:
            source = r["source"] if isinstance(r["source"], str) else json.dumps(r["source"])
            try:
                v = await judge.judge(r["prompt"], r["response"], [{
                    "name": "retrieve_documents", "args": {}, "result": source}])
                rec = {"id": r["id"], "flag": v.failure_class is not FailureClass.OK,
                       "class": v.failure_class.value, "rationale": v.rationale}
            except Exception as e:  # keep going; the row is retried on the next run
                print(f"  {r['id']}: {type(e).__name__}: {e}")
                return
        async with lock:
            done[r["id"]] = rec
            with OUT.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    await asyncio.gather(*(one(r) for r in todo))

    scored = [{**r, **done[r["id"]]} for r in rows if r["id"] in done]
    groups = collections.defaultdict(list)
    for r in scored:
        groups["ALL"].append(r)
        groups[r["model"]].append(r)
        groups[r["task"]].append(r)
    for k in ["ALL", *models, "QA", "Summary", "Data2txt"]:
        if groups[k]:
            print(f"{k:22s} {_metrics(groups[k])}")
    (HERE / out.replace("verdicts", "results").replace(".jsonl", ".json")).write_text(
        json.dumps({k: _metrics(v) for k, v in groups.items()}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gpt-4-0613", "gpt-3.5-turbo-0613"])
    ap.add_argument("--split", default="test")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--out", default="verdicts.jsonl")
    ap.add_argument("--sample", type=int, default=0, help="all bad answers + good ones up to N")
    ap.add_argument("--judge-model", default=None,
                    help="override OPENAI_MODEL (the shell env can't: config loads .env with override)")
    a = ap.parse_args()
    if a.judge_model:
        from cassandra_ai.config import get_settings
        get_settings().openai_model = a.judge_model
    asyncio.run(main(a.models, a.split, a.concurrency, a.out, a.sample))
