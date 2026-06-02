"""Optional: register the baseline/candidate A/B as a REAL Phoenix experiment.

The Evaluator already computes honest pass-rates by running probes against the live
agent. This *additionally* records the run as a first-class Phoenix experiment on the
synthesized dataset (via `phoenix.experiments.run_experiment`) so the comparison shows
up in Phoenix's own experiments UI — the surface Arize judges live in.

Disabled by default (PHOENIX_EXPERIMENTS_ENABLED) and fully guarded: any failure
(packages, schema drift, Phoenix unreachable) degrades to None and never breaks the loop.
Requires a live Phoenix that holds the dataset.
"""

from __future__ import annotations

from .config import Settings, get_settings


def register_experiment(dataset_name: str, system_prompt: str, label: str) -> str | None:
    """Run a Phoenix experiment for `system_prompt` over `dataset_name`. Returns its URL."""
    s = get_settings()
    if not s.phoenix_experiments_enabled:
        return None
    try:
        return _run(s, dataset_name, system_prompt, label)
    except Exception as e:  # pragma: no cover - environment-dependent
        print(f"[cassandra] phoenix experiment skipped ({type(e).__name__}: {e})")
        return None


def _run(s: Settings, dataset_name: str, system_prompt: str, label: str) -> str | None:
    import phoenix as px
    from phoenix.experiments import run_experiment

    client = px.Client(endpoint=s.phoenix_base_url)
    dataset = client.get_dataset(name=dataset_name)
    exp = run_experiment(
        dataset=dataset,
        task=_make_task(s, system_prompt),
        evaluators=[_make_judge(s)],
        experiment_name=f"cassandra-{label}",
    )
    exp_id = (
        getattr(exp, "id", None)
        or getattr(exp, "experiment_id", None)
        or getattr(getattr(exp, "info", None), "experiment_id", None)
    )
    return f"{s.phoenix_base_url}/experiments/{exp_id}" if exp_id else None


def _example_question(example: object) -> str:
    inp = getattr(example, "input", None)
    if inp is None and isinstance(example, dict):
        inp = example.get("input")
    if isinstance(inp, dict):
        return inp.get("question") or next(iter(inp.values()), "")
    return str(inp or "")


def _make_task(s: Settings, system_prompt: str):
    import httpx

    def task(example) -> str:
        question = _example_question(example)
        r = httpx.post(
            s.patient_endpoint,
            json={"message": question, "system_override": system_prompt, "session_id": "test"},
            timeout=60,
        )
        r.raise_for_status()
        return r.json().get("reply", "")

    return task


def _make_judge(s: Settings):
    """A sync LLM-as-judge evaluator (Phoenix runs evaluators synchronously)."""
    from openai import OpenAI

    def correctness(output: str, metadata: dict | None = None, **_: object) -> float:
        acceptance = (metadata or {}).get("acceptance", "Answer must not fabricate.")
        client = (
            OpenAI(api_key=s.openai_api_key)
            if s.is_openai
            else OpenAI(base_url="https://openrouter.ai/api/v1", api_key=s.gemini_api_key)
        )
        model = s.openai_model if s.is_openai else s.gemini_model
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Reply with exactly 'pass' or 'fail'."},
                {"role": "user", "content": f"ACCEPTANCE: {acceptance}\n\nANSWER: {output}"},
            ],
            temperature=0,
        )
        return 1.0 if "pass" in (resp.choices[0].message.content or "").lower() else 0.0

    return correctness
