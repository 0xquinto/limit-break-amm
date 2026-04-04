"""Verify all rendered prompts contain required XML wrapper tags."""
import re
from docs.orchestrator.config import WAVE_BH1
from docs.orchestrator.prompt_renderer import render_wave_prompts

REQUIRED_XML_TAGS = [
    "<preamble>",
    "</preamble>",
    "<checklist>",
    "</checklist>",
    "<injected_memory>",
    "</injected_memory>",
]


def test_rendered_prompts_contain_xml_tags():
    prompts = render_wave_prompts(WAVE_BH1)
    for agent_name, prompt in prompts.items():
        for tag in REQUIRED_XML_TAGS:
            assert tag in prompt, f"Agent {agent_name} missing XML tag: {tag}"


def test_rendered_prompts_have_archetype_root():
    prompts = render_wave_prompts(WAVE_BH1)
    for agent_name, prompt in prompts.items():
        assert "<agent_prompt" in prompt, f"Agent {agent_name} missing <agent_prompt> root tag"
        assert "</agent_prompt>" in prompt, f"Agent {agent_name} missing </agent_prompt> close tag"
