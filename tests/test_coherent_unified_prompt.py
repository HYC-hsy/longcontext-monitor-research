"""Approved unified prose and real request wiring; no live model quality claims."""
import ast
import asyncio
import hashlib
import inspect
from pathlib import Path

import pytest

from test_predictive_memory_read import Agent
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_predictive_visible_basis import install, provider_llm, rows
from memory_agent.memory import read_context_predictive_memory_agent as module
from memory_agent.memory.read_context_predictive_memory_agent import (
    BANK_TOOLS, PUBLIC_FORECAST_REMINDER, UNIFIED_SYSTEM)

EXPECTED_SYSTEM = '''You are the task's information organizer. Some information that appears during task execution remains valuable much later in the task, while other information only becomes valuable then. Your role is to predict and save this information, and remind the task agent when it is relevant to its current or upcoming work, helping it use existing information to complete the task.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

Based on the task description and the task agent's trajectory, carry out the following steps:

1. Predict and save. You must predict which information received this time will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns, and organize and save that information in the knowledge bank. Before saving, briefly state which information you have selected.

2. Recall and remind. After organizing the information for this wake, use memory_read to read the knowledge bank. Based on the task agent's current and upcoming work, decide whether to remind it of information in the knowledge bank.

## Tools
- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.

Organize information and decide whether to provide a reminder in this same conversation. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If a reminder is needed:
<context_for_action>
Information to remind the task agent of.
</context_for_action>

If no reminder is needed:
<no_intervention/>'''


def test_exact_approved_coherent_system():
    assert UNIFIED_SYSTEM == EXPECTED_SYSTEM
    assert "You help the task agent" not in UNIFIED_SYSTEM
    assert "Default to no intervention" not in UNIFIED_SYSTEM
    assert UNIFIED_SYSTEM.count("<no_intervention/>") == 1
    assert UNIFIED_SYSTEM.count("<context_for_action>") == 1


def nonprompt_digest(source):
    # Runtime AST pinned after the authorized reminder-first stage implementation.
    # Schemas, recovery, input wrappers and the tool loop remain protected.
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id in {'UNIFIED_SYSTEM', 'PUBLIC_FORECAST_REMINDER'} for target in node.targets):
            node.value = ast.Constant('PROMPT_VALUE_ONLY')
    # Python 3.13 omits empty lists by default; retain the 3.12 dump contract.
    options = {'show_empty': True} if 'show_empty' in inspect.signature(ast.dump).parameters else {}
    return hashlib.sha256(ast.dump(tree, include_attributes=False, **options).encode()).hexdigest()


def test_runtime_matches_pinned_reminder_first_implementation():
    assert nonprompt_digest(Path(module.__file__).read_text()) == '4fdcff3e80e8ad9dded20de0157538c8f10457714e9ca003c6dd81e531150711'


def test_nonprompt_guard_rejects_runtime_change():
    source = Path(module.__file__).read_text()
    changed = source.replace('MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS = 2', 'MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS = 3')
    assert changed != source
    assert nonprompt_digest(changed) != nonprompt_digest(source)


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


EXPECTED_PUBLIC_REMINDER = 'Briefly state which information you have selected that you predict will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns.'


def test_public_reminder_matches_information_forecast():
    assert PUBLIC_FORECAST_REMINDER == EXPECTED_PUBLIC_REMINDER
    assert "private reasoning" not in PUBLIC_FORECAST_REMINDER
    assert "do not disclose private reasoning" not in UNIFIED_SYSTEM
    for text in [UNIFIED_SYSTEM, PUBLIC_FORECAST_REMINDER]:
        assert 'problems or decisions' not in text
    assert 'will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns' in PUBLIC_FORECAST_REMINDER
    assert 'briefly state which information you have selected' in UNIFIED_SYSTEM
    assert 'information received this time' in UNIFIED_SYSTEM
    assert 'will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns' in UNIFIED_SYSTEM
    assert 'the task agent may use' not in UNIFIED_SYSTEM
    assert 'four turns' not in UNIFIED_SYSTEM
    assert 'four turns' not in PUBLIC_FORECAST_REMINDER
    assert 'briefly and directly' not in UNIFIED_SYSTEM


def test_completion_tags_remain_but_long_protocol_guidance_is_removed():
    assert UNIFIED_SYSTEM.endswith('<no_intervention/>')
    assert 'exactly one of the following decision tags' in UNIFIED_SYSTEM
    for removed in ['Use as many tool rounds', 'You may include the final decision',
                    'If a tool fails', 'Ordinary text or a tool call without']:
        assert removed not in UNIFIED_SYSTEM


def test_forecast_window_does_not_delay_related_reminders():
    selection = UNIFIED_SYSTEM.split('1. Predict and save.', 1)[1].split('2. Recall', 1)[0]
    assert 'will still be worth presenting to the task agent to support subsequent task work after the task has progressed for another eight turns' in selection
    assert 'organize and save that information' in selection
    reminder = UNIFIED_SYSTEM.split('2. Recall', 1)[1].split('## Tools', 1)[0]
    assert "task agent's current and upcoming work" in reminder
    assert 'After organizing the information for this wake, use memory_read' in reminder
    assert 'decide whether to remind it of information in the knowledge bank.' in reminder
    assert 'six task-agent turns' not in reminder
    for removed in ['already visible', 'taken it into account', 'Default to no intervention']:
        assert removed not in UNIFIED_SYSTEM


def test_information_organizer_role_and_separate_tool_guidance():
    role = UNIFIED_SYSTEM.split('\n\n', 1)[0]
    assert "task's information organizer" in role
    assert 'relevant to its current or upcoming work' in role
    assert 'useful now' not in role
    assert '## Tools\n- memory_add:' in UNIFIED_SYSTEM
    assert '- memory_read: Read all information currently saved' in UNIFIED_SYSTEM
    assert 'Set bank_id to "knowledge"' in UNIFIED_SYSTEM


def test_simple_selection_replaces_first_use_and_certainty_requirements():
    selection = UNIFIED_SYSTEM.split('1. Predict and save.', 1)[1].split('2. Recall', 1)[0]
    assert 'You must predict which information received this time' in selection
    assert 'organize and save that information' in selection
    assert 'Before saving, briefly state which information you have selected.' in selection
    for removed in ['first use', 'only after', 'confirmed findings', 'tentative inferences',
                    'level of certainty', 'levels of certainty', 'future uses', 'six task-agent']:
        assert removed not in selection
        assert removed not in PUBLIC_FORECAST_REMINDER
    assert 'Organize information and decide whether to provide a reminder in this same conversation.' in UNIFIED_SYSTEM


def test_recall_and_tool_contract_remain_current_work_based():
    reminder = UNIFIED_SYSTEM.split('2. Recall', 1)[1].split('## Tools', 1)[0]
    assert 'After organizing the information for this wake, use memory_read' in reminder
    assert "task agent's current and upcoming work" in reminder
    assert 'next eight' not in reminder


def test_recall_is_simple_model_decision_without_extra_rules():
    recall = UNIFIED_SYSTEM.split('2. Recall', 1)[1].split('## Tools', 1)[0]
    assert "including information inconsistent with its current judgment" not in recall
    assert "Preserve the information's original level of certainty." not in recall
    assert 'After organizing the information for this wake, use memory_read' in recall
    assert 'If you saved' not in recall
    assert 'eight' not in recall


def test_role_covers_persistent_and_delayed_value_without_first_use_gate():
    role = UNIFIED_SYSTEM.split('\n\n', 1)[0]
    assert 'remains valuable much later in the task' in role
    assert 'other information only becomes valuable then' in role
    assert 'first' not in UNIFIED_SYSTEM
    assert 'next eight' not in UNIFIED_SYSTEM
