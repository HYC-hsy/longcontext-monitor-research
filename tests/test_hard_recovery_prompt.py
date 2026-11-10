"""Prompt-only selection change; deterministic transport checks, not an efficacy test."""
import copy
import json

import pytest

from test_predictive_memory_read import Agent, run
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_predictive_visible_basis import provider_llm
from memory_agent.memory import predictive_memory_agent as legacy
from memory_agent.memory.read_context_predictive_memory_agent import (
    BANK_TOOLS, PHASE1_SYSTEM)


def test_only_read_context_tool_description_changes():
    expected_add = copy.deepcopy(legacy.BANK_TOOLS[0])
    expected_add['function']['description'] = 'Save information in the knowledge memory bank.'
    expected_add['function']['parameters']['additionalProperties'] = False
    assert BANK_TOOLS[0] == expected_add
    assert legacy.BANK_TOOLS[0]['function']['description'] == (
        'Save information expected to be useful within the next 10 turns.')
    assert 'next 10 turns' in legacy.PHASE1_SYSTEM
    assert 'additionalProperties' not in legacy.BANK_TOOLS[0]['function']['parameters']
    active_instructions = PHASE1_SYSTEM + json.dumps(BANK_TOOLS)
    for removed in ('10 turns', 'preserve', 'certainty', 'priorit', 'briefly explain',
                    'same response', 'may need', 'might need', 'possibly'):
        assert removed not in active_instructions


@pytest.mark.parametrize('provider', ['anthropic', 'openai'])
def test_exact_prompt_and_neutral_tools_reach_both_providers(provider, monkeypatch):
    llm, wire = provider_llm(provider, [
        {'text': '', 'calls': [('add-one', 'memory_add', {'content': 'retained detail'})]},
        {'text': '<no_intervention/>'}], monkeypatch)
    result = run(Agent(llm=llm))
    assert len(wire) == 2 and len(result.operations) == 1
    assert result.operations[0].success and not result.should_inject
    for index, expected in enumerate((PHASE1_SYSTEM, legacy.PHASE2_SYSTEM)):
        if provider == 'openai':
            actual = wire[index]['instructions']
        else:
            actual = wire[index]['system']
            if isinstance(actual, list):
                actual = ''.join(block['text'] for block in actual)
        assert actual == expected
    assert [tool['name'] for tool in wire[0]['tools']] == ['memory_add', 'memory_read']
    for actual, expected in zip(wire[0]['tools'], BANK_TOOLS):
        assert actual['description'] == expected['function']['description']
        schema_key = 'parameters' if provider == 'openai' else 'input_schema'
        assert actual[schema_key] == expected['function']['parameters']
    assert 'tools' not in wire[1]
    assert '10 turns' not in json.dumps(wire[0])
