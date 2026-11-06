"""cassandra/faithfulness.py — value check (no LLM) and claim-by-claim judge (LLM mocked)."""

from __future__ import annotations

import pytest

from cassandra.faithfulness import Claim, ClaimReport, claim_check, value_check

HOURS = {"name": "Patxi's", "business_stars": 4.0,
         "hours": {"Monday": "12:0-21:0", "Friday": "12:0-23:0"}}


def _vals(answer, source=HOURS):
    return [i.value for i in value_check(answer, source)]


def test_matching_times_and_rating_pass():
    assert _vals("A 4-star spot, open 12:00 PM to 9:00 PM, Fridays until 11 PM.") == []


def test_wrong_closing_time_is_flagged():
    assert _vals("Open from 12 PM to 10 PM.") == ["10 PM"]


def test_wrong_rating_is_flagged():
    assert _vals("Rated 4.5 stars.") == ["4.5"]


def test_12h_time_is_not_reread_as_a_24h_morning_time():
    # "9:00 PM" must not also be checked as 09:00, which the source doesn't have
    assert _vals("Closes at 9:00 PM.") == []


def test_small_counts_and_hyphenated_tokens_are_ignored():
    assert _vals("Open 7 days a week, with COVID-19 measures.") == []


def test_times_unchecked_when_source_has_no_times():
    assert _vals("Opens at 10 AM.", {"name": "x"}) == []


def test_numbers_anywhere_in_a_text_source_count():
    assert _vals("Revenue rose to 1,200 units in 2015.", "In 2015 it sold 1200 units.") == []


@pytest.mark.asyncio
async def test_claim_check_passes_source_and_reports_unsupported(monkeypatch):
    seen = {}

    async def fake_structured(prompt, schema, **kw):
        seen["prompt"], seen["system"] = prompt, kw.get("system", "")
        return ClaimReport(claims=[
            Claim(claim="Open until 9 PM", status="supported"),
            Claim(claim="No music", status="not_in_source"),
            Claim(claim="A lovely spot", status="opinion"),
            Claim(claim="Rated 4.5", status="contradicted"),
        ])

    monkeypatch.setattr("cassandra.faithfulness.llm.structured", fake_structured)
    rep = await claim_check("Describe it", "answer text", HOURS)
    assert [c.claim for c in rep.unsupported] == ["No music", "Rated 4.5"]
    assert '"business_stars": 4.0' in seen["prompt"] and "answer text" in seen["prompt"]
    assert "UNKNOWN, not \"no\"" in seen["system"]
