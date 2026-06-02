"""Validate the ADK runtime shell builds (skips if google-adk isn't installed)."""

import pytest

pytest.importorskip("google.adk", reason="google-adk not installed in this env")


def test_build_adk_agent_wires_a_real_sub_agent():
    from cassandra.loop_agent import build_adk_agent

    agent = build_adk_agent()
    assert agent.name == "cassandra"
    assert agent.max_iterations == 1
    # The sub-agent must be a genuine ADK agent, not an empty placeholder.
    assert len(agent.sub_agents) == 1
    assert agent.sub_agents[0].name == "supervision_cycle"
    assert hasattr(agent.sub_agents[0], "_run_async_impl")
