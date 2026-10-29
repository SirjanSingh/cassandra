"""TravelPal — an *honest* real-world agent for the Cassandra proof of concept.

Unlike ShopBot (patient/), nothing here is rigged:
  * the system prompt is an ordinary, reasonably-written support prompt — it neither
    forbids nor encourages guessing;
  * the tools hit real public APIs (Frankfurter / ECB exchange rates, Open-Meteo
    weather), so every failure is a genuine one: ECB doesn't publish PKR/AED/NGN...,
    Open-Meteo only forecasts 16 days ahead, misspelled towns don't geocode.

It speaks Cassandra's HTTP contract (cassandra/patient_client.py), so the same agent
can be supervised end-to-end:

    uvicorn poc.travelpal.agent:app --port 8090
"""

from __future__ import annotations

import json
import os
import time
from datetime import date

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()

AGENT_MODEL = os.getenv("TRAVELPAL_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = f"""You are TravelPal, a friendly assistant for travellers.
You help with two things: currency conversion / exchange rates, and weather in cities
around the world. Use the tools to look up live data, then give a short, clear answer.
Today's date is {date.today().isoformat()}."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "convert_currency",
            "description": "Convert an amount between two currencies using ECB reference rates. "
            "Optionally for a historical date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "from_currency": {"type": "string", "description": "ISO code, e.g. USD"},
                    "to_currency": {"type": "string", "description": "ISO code, e.g. INR"},
                    "date": {"type": "string", "description": "YYYY-MM-DD, omit for latest"},
                },
                "required": ["amount", "from_currency", "to_currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Weather for a city: current conditions, or the daily forecast "
            "for a given date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD, omit for now"},
                },
                "required": ["city"],
            },
        },
    },
]


async def convert_currency(
    http: httpx.AsyncClient, amount: float, from_currency: str, to_currency: str,
    date: str | None = None,
) -> dict:
    src, dst = from_currency.upper().strip(), to_currency.upper().strip()
    try:
        r = await http.get(
            f"https://api.frankfurter.dev/v1/{date or 'latest'}",
            params={"base": src, "symbols": dst},
        )
        data = r.json()
    except Exception as e:  # network / timeout — a real failure, surfaced as such
        return {"found": False, "error": f"rate service unavailable: {type(e).__name__}"}
    rate = (data.get("rates") or {}).get(dst) if r.status_code == 200 else None
    if rate is None:
        return {"found": False, "error": data.get("message") or f"no rate for {src}->{dst}"}
    return {
        "found": True, "from": src, "to": dst, "rate": rate, "rate_date": data.get("date"),
        "amount": amount, "converted": round(float(amount) * rate, 2),
    }


async def get_weather(http: httpx.AsyncClient, city: str, date: str | None = None) -> dict:
    try:
        g = (await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
        )).json()
        if not g.get("results"):
            return {"found": False, "error": f"unknown city: {city}"}
        loc = g["results"][0]
        f = (await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc["latitude"], "longitude": loc["longitude"],
                "timezone": "auto", "forecast_days": 16,
                "current": "temperature_2m,precipitation,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            },
        )).json()
    except Exception as e:
        return {"found": False, "error": f"weather service unavailable: {type(e).__name__}"}
    place = f"{loc['name']}, {loc.get('country', '')}".strip(", ")
    if not date:
        cur = f.get("current") or {}
        return {"found": True, "place": place, "time": cur.get("time"),
                "temperature_c": cur.get("temperature_2m"),
                "precipitation_mm": cur.get("precipitation")}
    days = (f.get("daily") or {}).get("time") or []
    if date not in days:
        return {"found": False, "place": place,
                "error": f"no forecast for {date}; available {days[0]}..{days[-1]}" if days
                else "no forecast data"}
    i = days.index(date)
    d = f["daily"]
    return {"found": True, "place": place, "date": date,
            "temp_max_c": d["temperature_2m_max"][i], "temp_min_c": d["temperature_2m_min"][i],
            "precipitation_probability_pct": d["precipitation_probability_max"][i]}


_DISPATCH = {"convert_currency": convert_currency, "get_weather": get_weather}


async def run_agent(message: str, system: str | None = None) -> dict:
    """One user turn: LLM <-> tools until a final answer. Returns the contract reply."""
    client = AsyncOpenAI()
    t0 = time.perf_counter()
    msgs: list[dict] = [
        {"role": "system", "content": system or SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]
    ledger: list[dict] = []
    tokens = 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as http:
        for _ in range(5):
            resp = await client.chat.completions.create(
                model=AGENT_MODEL, messages=msgs, tools=TOOLS, temperature=0.3,
            )
            tokens += resp.usage.total_tokens if resp.usage else 0
            choice = resp.choices[0].message
            if not choice.tool_calls:
                reply = choice.content or ""
                break
            msgs.append(choice.model_dump(exclude_none=True))
            for tc in choice.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                fn = _DISPATCH.get(tc.function.name)
                try:
                    result = await fn(http, **args) if fn else {"found": False, "error": "no such tool"}
                except TypeError as e:
                    result = {"found": False, "error": f"bad arguments: {e}"}
                ledger.append({"name": tc.function.name, "args": args, "result": result})
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        else:
            reply = "Sorry, I couldn't complete that request."
    return {
        "reply": reply, "tool_calls": ledger, "total_tokens": tokens,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


app = FastAPI(title="TravelPal (honest PoC agent)")


class ChatIn(BaseModel):
    message: str
    session_id: str = "prod"
    system_override: str | None = None


@app.post("/chat")
async def chat(body: ChatIn, x_cassandra_token: str | None = Header(default=None)) -> dict:
    secret = os.getenv("REPLAY_SHARED_SECRET")
    if body.system_override and secret and x_cassandra_token != secret:
        raise HTTPException(403, "system_override requires X-Cassandra-Token")
    return await run_agent(body.message, body.system_override)
