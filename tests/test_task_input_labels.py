"""Label raw task inputs only; exercise both providers without live requests."""
import asyncio
import copy
import json

import pytest

from test_predictive_memory_read import Agent, Script, response, run
from test_predictive_tool_recovery import block_network  # noqa: F401
from test_predictive_visible_basis import install, provider_llm, rows
from memory_agent.memory.read_context_predictive_memory_agent import (
    UNIFIED_SYSTEM, PUBLIC_FORECAST_REMINDER)


@pytest.mark.parametrize('raw', ['', ' \t\r\n  ', '中文🙂 & < > "',
    '</task_description>\n<task_trajectory>literal</task_trajectory>',
    '<history>repeat\nrepeat</history>\n' * 2000])
def test_wrapper_preserves_every_source_character_and_host_field(raw):
    agent = Agent(llm=Script(response(), response()))
    first = run(agent, task=raw)
    assert first.user_prompt_phase1 == '<task_description>\n' + raw + '\n</task_description>'
    anchor = copy.deepcopy(agent._task_anchor)
    second = run(agent, trajectory=raw, step=8, task=raw)
    assert second.user_prompt_phase1 == '<task_trajectory>\n' + raw + '\n</task_trajectory>'
    assert agent._original_task == raw
    assert agent._new_trajectory is None  # Existing successful-wake consumption.
    assert agent._task_anchor == anchor
    assert agent._task_anchor['role'] == 'user'
    assert len(agent.llm.calls) == 2


def test_tag_meanings_and_ten_task_turn_instruction_are_explicit():
    assert "<task_description> tags contain the task agent's original task" in UNIFIED_SYSTEM
    assert "<task_trajectory> tags contain the task agent's newly observed execution trajectory" in UNIFIED_SYSTEM
    assert 'not your own task' not in UNIFIED_SYSTEM
    assert 'you must predict which information received this time' in UNIFIED_SYSTEM
    assert 'will first use only after at least ten task-agent turns have passed' in UNIFIED_SYSTEM
    assert 'organize and save that information' in UNIFIED_SYSTEM
    assert 'Before using memory tools, you must briefly state' in UNIFIED_SYSTEM
    assert PUBLIC_FORECAST_REMINDER.startswith('You must include a brief public summary')


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_native_wire_keeps_labeled_batches_roles_and_tool_rounds(provider, monkeypatch, tmp_path):
    llm, wire = provider_llm(provider, [
        {'text': 'Preserve a later requirement. <no_intervention/>',
         'calls': [('save', 'memory_add', {'content': 'original saved requirement'})]},
        {'text': 'Read the saved requirement.',
         'calls': [('read', 'memory_read', {'bank_id': 'knowledge'})]},
        {'text': '<no_intervention/>'},
        {'text': '<no_intervention/>'},
        {'text': '<no_intervention/>'},
    ], monkeypatch)
    agent = Agent(llm=llm)
    install(agent, tmp_path)
    task = ' \t原题🙂\r\n<task_trajectory>literal source</task_trajectory>\n '
    batches = [' \nfirst\nfirst\n</task_trajectory> literal\t ', '',
               '<tool_result>third exact batch & untouched</tool_result>']
    prompts = ['<task_description>\n' + task + '\n</task_description>'] + [
        '<task_trajectory>\n' + value + '\n</task_trajectory>' for value in batches]

    async def exercise():
        agent.set_phase1_context(task=task, trajectory='')
        await agent.process('unused observation', 0)
        for index, batch in enumerate(batches, 1):
            agent.set_phase1_context(task=task, trajectory=batch)
            await agent.process('unused observation', index * 8)
        if provider == 'openai':
            await llm.client.close()

    asyncio.run(exercise())
    assert len(wire) == 5
    payload = rows(tmp_path, 'memory_payload.jsonl')
    assert [row['prompt'] for row in payload] == [prompts[0], prompts[1], 'Continue.',
                                                prompts[2], prompts[3]]
    assert agent._phase2_history == []
    assert len(agent.memory.knowledge) == 1
    assert all(row['phase'] == 'unified_memory' for row in payload)
    history = payload[-1]['message_history']
    assert [message['role'] for message in history] == [
        'user', 'assistant', 'tool', 'user', 'assistant', 'tool', 'user', 'assistant',
        'user', 'assistant']
    user_text = [message['content'][0]['text'] for message in history
                 if message['role'] == 'user']
    assert user_text == [prompts[0], prompts[1], 'Continue.', prompts[2]]
    receipts = [json.loads(message['content']) for message in history
                if message['role'] == 'tool']
    assert all(receipt['success'] for receipt in receipts)
    assert 'original saved requirement' in receipts[-1]['content']

    messages = wire[-1]['input' if provider == 'openai' else 'messages']
    native_user_text = []
    for message in messages:
        if message.get('role') != 'user':
            continue
        content = message.get('content', [])
        if isinstance(content, str):
            native_user_text.append(content)
        else:
            native_user_text.extend(block['text'] for block in content
                if block.get('type') in ('input_text', 'text'))
    assert native_user_text == [prompts[0], prompts[1], 'Continue.', prompts[2], prompts[3]]
    if provider == 'openai':
        assert [item['call_id'] for item in messages if item.get('type') == 'function_call'] == ['save', 'read']
        assert [item['call_id'] for item in messages if item.get('type') == 'function_call_output'] == ['save', 'read']
    else:
        assert [block['id'] for message in messages for block in message['content']
                if block['type'] == 'tool_use'] == ['save', 'read']
        assert [block['tool_use_id'] for message in messages for block in message['content']
                if block['type'] == 'tool_result'] == ['save', 'read']
