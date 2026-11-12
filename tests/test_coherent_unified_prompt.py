"""Approved unified prose and real request wiring; no live model quality claims."""
import ast
import asyncio
import hashlib
from pathlib import Path

import pytest

from test_predictive_memory_read import Agent
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_predictive_visible_basis import install, provider_llm, rows
from memory_agent.memory import read_context_predictive_memory_agent as module
from memory_agent.memory.read_context_predictive_memory_agent import (
    BANK_TOOLS, PUBLIC_FORECAST_REMINDER, UNIFIED_SYSTEM)

EXPECTED_SYSTEM = '''You are the task agent's information organizer, responsible for organizing and preserving information it will need in the future and reminding it when that information is relevant to its current work.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time the task agent will first use only after at least ten task-agent turns have passed. Before saving, you must briefly explain which information you considered and how it will be used in the future, distinguishing confirmed findings from tentative inferences. Save only confirmed findings.

2. Recall relevant information. On every wake, use memory_read with bank_id="knowledge" to read the knowledge bank. From the returned information, select what is relevant to the task agent's current work and provide it briefly and directly for its next turn. If there is no relevant information, provide none. Do not take over the task agent's work.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.

Organize information and recall relevant knowledge in this same conversation. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If there is relevant information:
<context_for_action>
Relevant information for the task agent's next turn.
</context_for_action>

If there is no relevant information:
<no_intervention/>'''


def test_exact_approved_coherent_system():
    assert UNIFIED_SYSTEM == EXPECTED_SYSTEM
    assert "You help the task agent" not in UNIFIED_SYSTEM
    assert "Default to no intervention" not in UNIFIED_SYSTEM
    assert UNIFIED_SYSTEM.count("<no_intervention/>") == 1
    assert UNIFIED_SYSTEM.count("<context_for_action>") == 1


def test_only_unified_system_changes_from_pinned_parent():
    # AST at 10fe52e after masking only UNIFIED_SYSTEM. This also protects
    # soft reminder, schemas, recovery, input wrappers and the tool loop.
    tree = ast.parse(Path(module.__file__).read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == 'UNIFIED_SYSTEM' for target in node.targets):
            node.value = ast.Constant('PROMPT_VALUE_ONLY')
    digest = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    assert digest == 'aa92c638efefe527e1b7b82e582affefc4361abe0323e8037e2db0cff6ffcb97'


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_actual_system_prompt_and_continuation_are_coherent(provider, monkeypatch, tmp_path):
    # First wake finishes with add+tag. Its absent public summary can only
    # remind the next already-scheduled request, never force an extra call.
    llm, wire = provider_llm(provider, [
        {'text': '<no_intervention/>', 'calls': [('a1', 'memory_add', {
            'content': 'The task specifies the endpoint /v1.'})]},
        {'text': 'I will read the saved endpoint before the next request.',
         'calls': [('r1', 'memory_read', {'bank_id': 'knowledge'})]},
        {'text': '<context_for_action>The task specifies the endpoint /v1.</context_for_action>'},
    ], monkeypatch)
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    task = 'Exact original task <history>literal task text</history>'
    batch = 'Exact new public trajectory: prepare the endpoint request.'

    async def exercise():
        agent.set_phase1_context(task=task, trajectory='')
        first = await agent.process('MUST NOT ENTER A SECOND PHASE', 0)
        assert first.termination == 'no_intervention' and len(wire) == 1
        agent.set_phase1_context(task=task, trajectory=batch)
        second = await agent.process('MUST NOT ENTER A SECOND PHASE', 8)
        if provider == 'openai':
            await llm.client.close()
        return second

    result = asyncio.run(exercise())
    assert len(wire) == 3 and result.should_inject
    assert result.loop_mode == 'unified' and len(result.loop_rounds) == 2
    assert result.loop_rounds[0]['decision_accepted'] is False
    assert result.loop_rounds[1]['decision_accepted'] is True
    assert result.context_for_action == 'The task specifies the endpoint /v1.'
    assert agent._phase2_history == []
    assert result.user_prompt_phase2 is result.raw_response_phase2 is None
    expected = [EXPECTED_SYSTEM, EXPECTED_SYSTEM + '\n\n' + PUBLIC_FORECAST_REMINDER,
                EXPECTED_SYSTEM]
    actual = ([request['instructions'] for request in wire] if provider == 'openai'
              else [''.join(block['text'] for block in request['system']) for request in wire])
    assert actual == expected
    payload = rows(tmp_path, 'memory_payload.jsonl')
    assert [request['system'] for request in payload] == expected
    assert [request['prompt'] for request in payload] == [
        '<task_description>\n' + task + '\n</task_description>',
        '<task_trajectory>\n' + batch + '\n</task_trajectory>', 'Continue.']
    assert all(request['tools'] == BANK_TOOLS for request in payload)
    assert all(request['phase'] == 'unified_memory' for request in payload)
    history = payload[-1]['message_history']
    assert any(message.get('tool_call_id') == 'r1' for message in history)
    assert 'The task specifies the endpoint /v1.' in str(history)
    assert 'MUST NOT ENTER A SECOND PHASE' not in str(payload)
    assert 'private-fixture' not in str(payload)


EXPECTED_PUBLIC_REMINDER = 'You must include a brief public summary of the information you plan to preserve and how you anticipate it will be useful in work after ten task-agent turns have passed.'


def test_public_reminder_matches_information_forecast():
    assert PUBLIC_FORECAST_REMINDER == EXPECTED_PUBLIC_REMINDER
    assert "private reasoning" not in PUBLIC_FORECAST_REMINDER
    assert "do not disclose private reasoning" not in UNIFIED_SYSTEM
    for text in [UNIFIED_SYSTEM, PUBLIC_FORECAST_REMINDER]:
        assert 'problems or decisions' not in text
    assert 'how you anticipate it will be useful in work after ten task-agent turns have passed' in PUBLIC_FORECAST_REMINDER
    assert 'how it will be used in the future' in UNIFIED_SYSTEM
    assert 'information received this time' in UNIFIED_SYSTEM
    assert 'the task agent will first use only after at least ten task-agent turns have passed' in UNIFIED_SYSTEM
    assert 'the task agent may use' not in UNIFIED_SYSTEM
    assert 'four turns' not in UNIFIED_SYSTEM
    assert 'four turns' not in PUBLIC_FORECAST_REMINDER
    assert 'briefly and directly' in UNIFIED_SYSTEM


def test_completion_tags_remain_but_long_protocol_guidance_is_removed():
    assert UNIFIED_SYSTEM.endswith('<no_intervention/>')
    assert 'exactly one of the following decision tags' in UNIFIED_SYSTEM
    for removed in ['Use as many tool rounds', 'You may include the final decision',
                    'If a tool fails', 'Ordinary text or a tool call without']:
        assert removed not in UNIFIED_SYSTEM


def test_first_use_guidance_does_not_delay_related_reminders():
    selection = UNIFIED_SYSTEM.split('1. Predict and save.', 1)[1].split('2. Recall', 1)[0]
    assert 'will first use only after at least ten task-agent turns have passed' in selection
    assert 'Save only confirmed findings.' in selection
    reminder = UNIFIED_SYSTEM.split('2. Recall', 1)[1].split('## Tools', 1)[0]
    assert "select what is relevant to the task agent's current work" in reminder
    assert 'On every wake, use memory_read with bank_id="knowledge"' in reminder
    assert 'If there is no relevant information, provide none.' in reminder
    assert 'ten task-agent turns' not in reminder
    for removed in ['already visible', 'taken it into account', 'Default to no intervention']:
        assert removed not in UNIFIED_SYSTEM


def test_information_organizer_role_and_separate_tool_guidance():
    role = UNIFIED_SYSTEM.split('\n\n', 1)[0]
    assert "task agent's information organizer" in role
    assert 'relevant to its current work' in role
    assert 'useful now' not in role
    assert '## Tools\n- memory_add:' in UNIFIED_SYSTEM
    assert '- memory_read: Read all information currently saved' in UNIFIED_SYSTEM
    assert 'Set bank_id to "knowledge"' in UNIFIED_SYSTEM


def test_confirmed_content_rule_does_not_require_verified_future_use():
    assert 'Before saving, you must briefly explain which information you considered' in UNIFIED_SYSTEM
    assert 'distinguishing confirmed findings from tentative inferences' in UNIFIED_SYSTEM
    assert 'Save only confirmed findings.' in UNIFIED_SYSTEM
    assert 'Save only information explicitly provided in the task description' not in UNIFIED_SYSTEM
    assert 'Preserve their scope' not in UNIFIED_SYSTEM
    assert 'how it will be used in the future' in UNIFIED_SYSTEM
    assert 'Organize information and recall relevant knowledge in this same conversation.' in UNIFIED_SYSTEM
    assert 'Manage memory and decide whether' not in UNIFIED_SYSTEM
