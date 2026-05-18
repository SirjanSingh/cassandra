"""Dashboard service (FR-DB1..DB5).

Serves the built React cockpit (web/dist), streams pipeline events over SSE,
and proxies the "send customer message" box to the Patient so the whole loop is
driveable live on camera.

Build the UI with:  cd web && npm install && npm run build
In dev, run Vite (`npm run dev`) which proxies /events and /ask here.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from cassandra.config import get_settings
from cassandra.events import bus

app = FastAPI(title="Cassandra Dashboard")

_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"


class Ask(BaseModel):
    message: str


@app.get("/events")
async def events():
    async def gen():
        async for ev in bus.subscribe():
            yield {"event": "pipeline", "data": json.dumps(ev.model_dump(mode="json"))}

    return EventSourceResponse(gen())


@app.post("/ask")
async def ask(req: Ask) -> dict:
    """Drive the demo: send a customer message to the Patient (FR-DB3)."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(s.patient_endpoint, json={"message": req.message})
        r.raise_for_status()
        return r.json()


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "service": "dashboard", "built": _DIST.is_dir()}


# Serve the built SPA last so /events, /ask, /healthz keep priority.
# html=True gives SPA fallback to index.html for client-side routing.
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
else:

    @app.get("/", response_class=HTMLResponse)
    async def _unbuilt() -> str:
        return (
            "<body style='background:#070707;color:#F4F1EA;font-family:monospace;"
            "padding:48px;line-height:1.6'>"
            "<h1>Cassandra cockpit not built</h1>"
            "<p>Run <code>cd web &amp;&amp; npm install &amp;&amp; npm run build</code>, "
            "then restart this service.</p>"
            "<p>Or run the Vite dev server: <code>cd web &amp;&amp; npm run dev</code> "
            "(it proxies /events and /ask here).</p></body>"
        )
