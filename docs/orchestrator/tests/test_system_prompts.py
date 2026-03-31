"""Tests for per-archetype system prompt dispatcher and builders."""
import pytest
from unittest.mock import MagicMock

from docs.orchestrator.wave_runner import _get_system_prompt
from docs.orchestrator.templates.exploit_system_prompts import EXPLOIT_BASE_PROMPTS
from docs.orchestrator.templates.compliance_system_prompts import COMPLIANCE_BASE_PROMPTS
from docs.orchestrator.templates.boundary_system_prompts import BOUNDARY_BASE_PROMPTS
from docs.orchestrator.model_profiles import AUDIT_SYSTEM_PROMPT


def _mock_agent(name: str, scope: list[str] | None = None):
    agent = MagicMock()
    agent.name = name
    agent.scope = scope or ["lbamm-core"]
    return agent


class TestGetSystemPrompt:
    """_get_system_prompt() routes agents to the correct builder."""

    def test_exploit_agent_gets_exploit_prompt(self):
        agent = _mock_agent("math-exploiter", ["lbamm-core"])
        result = _get_system_prompt(agent)
        assert "math-exploiter" in result
        assert "exploit" in result.lower()
        assert len(result) > 200  # base + knowledge, not the 81-token fallback

    def test_compliance_agent_gets_compliance_prompt(self):
        agent = _mock_agent("precision-sniper", ["lbamm-core"])
        result = _get_system_prompt(agent)
        assert "precision-sniper" in result
        assert "failure classification" in result.lower() or "tactical" in result.lower()
        assert len(result) > 200

    def test_boundary_agent_gets_boundary_prompt(self):
        agent = _mock_agent("knowledge-gen-core-pooltype")
        result = _get_system_prompt(agent)
        assert "Core" in result and "Pool Type" in result
        assert len(result) > 200

    def test_unknown_agent_gets_generic_fallback(self):
        agent = _mock_agent("totally-unknown-agent-xyz")
        result = _get_system_prompt(agent)
        assert result == AUDIT_SYSTEM_PROMPT

    def test_exploit_takes_priority_over_compliance(self):
        """If an agent name existed in both dicts, exploit wins."""
        agent = _mock_agent("math-exploiter")
        result = _get_system_prompt(agent)
        assert "Write Forge tests that demonstrate attacker profit" in result or "exploit" in result.lower()

    def test_all_compliance_agents_return_nonempty(self):
        for name in COMPLIANCE_BASE_PROMPTS:
            agent = _mock_agent(name, ["lbamm-core"])
            result = _get_system_prompt(agent)
            assert result, f"Empty system prompt for compliance agent {name}"
            assert len(result) > 100, f"Suspiciously short prompt for {name}: {len(result)} chars"

    def test_all_exploit_agents_return_nonempty(self):
        for name in EXPLOIT_BASE_PROMPTS:
            agent = _mock_agent(name, ["lbamm-core"])
            result = _get_system_prompt(agent)
            assert result, f"Empty system prompt for exploit agent {name}"

    def test_all_boundary_agents_return_nonempty(self):
        for name in BOUNDARY_BASE_PROMPTS:
            agent = _mock_agent(name)
            result = _get_system_prompt(agent)
            assert result, f"Empty system prompt for boundary agent {name}"


from docs.orchestrator.config import WAVE_BH1, WAVE_EXPLOIT


class TestConfigPromptAlignment:
    """Every configured agent must have a system prompt — no silent fallback."""

    def test_wave_bh1_agents_all_have_prompts(self):
        all_prompt_keys = (
            set(EXPLOIT_BASE_PROMPTS.keys())
            | set(COMPLIANCE_BASE_PROMPTS.keys())
            | set(BOUNDARY_BASE_PROMPTS.keys())
        )
        for agent in WAVE_BH1.agents:
            assert agent.name in all_prompt_keys, (
                f"Agent '{agent.name}' in WAVE_BH1 has no system prompt. "
                f"Will silently fall back to generic AUDIT_SYSTEM_PROMPT."
            )

    def test_wave_exploit_agents_all_have_prompts(self):
        for agent in WAVE_EXPLOIT.agents:
            assert agent.name in EXPLOIT_BASE_PROMPTS, (
                f"Exploit agent '{agent.name}' not in EXPLOIT_BASE_PROMPTS. "
                f"Will fall through to compliance or generic prompt."
            )


class TestSpawnValidation:
    """System prompt must be validated before agent spawn."""

    def test_get_system_prompt_returns_string(self):
        for name in list(COMPLIANCE_BASE_PROMPTS) + list(EXPLOIT_BASE_PROMPTS) + list(BOUNDARY_BASE_PROMPTS):
            agent = _mock_agent(name, ["lbamm-core"])
            result = _get_system_prompt(agent)
            assert isinstance(result, str)
            assert len(result) > 0
