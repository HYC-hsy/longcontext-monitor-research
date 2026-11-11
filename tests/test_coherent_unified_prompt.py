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

EXPECTED_SYSTEM = '''You are the task agent's memory manager, responsible for preserving information it may need next and reminding it at appropriate times when that information can help its current work.

Based on the task description and the task agent's trajectory, anticipate the problems it may encounter, the decisions it may need to make, and the information it will need over the next 10 turns; organize and save information accordingly. At the same time, consider the task requirements and recent trajectory to decide whether any information already in memory needs to be brought to the agent's attention now.

Before using memory tools, briefly state in ordinary reply text the problems or decisions you anticipate and the information you plan to preserve for them. Give a concise public summary; no special format is needed, and do not disclose private reasoning. Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".

When giving a reminder, you may synthesize information, identify connections, and offer grounded inferences or suggestions; preserve the information's original uncertainty when expressing them. Default to no intervention: do not intervene if no reminder is needed now, or if the relevant information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account. Do not take over the task agent's work.

Manage memory and decide whether to give a reminder in this same conversation. Use as many tool rounds as needed, but do not add a round just to finish. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If a reminder is needed:
<context_for_action>
Relevant information to bring to the agent's attention.
</context_for_action>

If no reminder is needed:
<no_intervention/>

You may include the final decision in the same response as memory tools, but it takes effect only after every tool in that response succeeds. If a tool fails, use its returned error to correct the call or revise your decision in a later reply. If a memory_read result is needed to make your decision, call the tool without a final decision tag, then decide after seeing its result. Ordinary text or a tool call without a valid decision tag does not finish the wake.'''


def test_exact_approved_coherent_system():
    assert UNIFIED_SYSTEM == EXPECTED_SYSTEM
    assert "You help the task agent" not in UNIFIED_SYSTEM
    assert UNIFIED_SYSTEM.count("Default to no intervention") == 1
    assert UNIFIED_SYSTEM.count("<no_intervention/>") == 1
    assert UNIFIED_SYSTEM.count("<context_for_action>") == 1


def test_only_unified_prompt_ast_changes_from_pinned_parent():
    # SHA-256 of the AST at 352280922aa2b3746bad857452d471e465a5b4a6
    # after replacing only UNIFIED_SYSTEM's value with this same sentinel.
    tree = ast.parse(Path(module.__file__).read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'UNIFIED_SYSTEM'
                for target in node.targets))
    assignment.value = ast.Constant('PROMPT_VALUE_ONLY')
    digest = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    assert digest == '9504f0adfb4d1c40a16674506182d56cb7723d4842f84d31ce8daf41a6986e57'


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_actual_system_prompt_and_continuation_are_coherent(provider, monkeypatch, tmp_path):
    # First wake finishes with add+tag. Its absent public summary can only
    # remind the next already-scheduled request, never force an extra call.
    llm, wire = provider_llm(provider, [
        {'text': '<no_intervention/>', 'calls': [('a1', 'memory_add', {
            'content': 'The endpoint may be /v1; this is not confirmed.'})]},
        {'text': 'I will read the possible endpoint before the next request.',
         'calls': [('r1', 'memory_read', {'bank_id': 'knowledge'})]},
        {'text': '<context_for_action>The endpoint may be /v1; verify it before use.</context_for_action>'},
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
    assert result.context_for_action == 'The endpoint may be /v1; verify it before use.'
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
        '[Task Description]\n' + task, batch, 'Continue.']
    assert all(request['tools'] == BANK_TOOLS for request in payload)
    assert all(request['phase'] == 'unified_memory' for request in payload)
    history = payload[-1]['message_history']
    assert any(message.get('tool_call_id') == 'r1' for message in history)
    assert 'The endpoint may be /v1; this is not confirmed.' in str(history)
    assert 'MUST NOT ENTER A SECOND PHASE' not in str(payload)
    assert 'private-fixture' not in str(payload)
