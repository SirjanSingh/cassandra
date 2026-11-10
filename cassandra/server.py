"""`cassandra serve`: the checks as an HTTP API, so a bot can check answers live.

    POST /v1/check   {"question", "answer", "tool_calls", "context", "use_llm": true}
      → {"verdict": "flagged" | "ok" | "declined" | "unchecked", "findings": [...], ...}
    GET  /health

Self-hosted: run it next to the bot; nothing leaves the network except the claim check's
call to the LLM endpoint you configured (which can itself be local). Set CASSANDRA_API_KEY
to require `Authorization: Bearer <key>`. Needs `pip install "cassandra-ai[serve]"`.
"""

from __future__ import annotations

import hmac
from typing import Any

from pydantic import BaseModel, Field

from . import __version__
from .engine import check_turn
from .config import get_settings
from .grounding import GroundingSpec, load_spec
from .llm import LLMUnavailable
from .models import Finding, Layer, Turn, Verdict


class CheckRequest(BaseModel):
    id: str = ""
    question: str = ""
    answer: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    context: str | list[Any] | dict[str, Any] | None = None
    use_llm: bool = True


class CheckResponse(BaseModel):
    id: str
    verdict: Verdict
    findings: list[Finding]
    layers: list[Layer]
    note: str = ""


def create_app(spec: GroundingSpec | None = None):
    from fastapi import Depends, FastAPI, Header, HTTPException

    s = get_settings()
    if spec is None and s.spec_file:
        spec = load_spec(s.spec_file)

    def auth(authorization: str | None = Header(default=None)) -> None:
        if not s.api_key:
            return
        expected = f"Bearer {s.api_key}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="missing or wrong API key")

    app = FastAPI(title="Cassandra", version=__version__,
                  description="Checks a bot's answer against the data it was given.")

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "version": __version__, "llm": s.llm_configured,
                "spec": spec is not None}

    @app.post("/v1/check", response_model=CheckResponse, dependencies=[Depends(auth)])
    async def check(req: CheckRequest) -> CheckResponse:
        turn = Turn(id=req.id, question=req.question, answer=req.answer,
                    tool_calls=req.tool_calls, context=req.context)
        try:
            r = await check_turn(turn, spec, use_llm=req.use_llm and s.llm_configured)
        except LLMUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        return CheckResponse(id=req.id, verdict=r.verdict, findings=r.findings,
                             layers=r.layers, note=r.note)

    return app
