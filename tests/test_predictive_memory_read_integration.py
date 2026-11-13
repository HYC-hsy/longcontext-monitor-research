"""Pinned adapter and host contracts with an in-process synthetic completion."""
import ast
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_predictive_memory_read import Agent, Script, call, response, run
from memory_agent.memory.ga_context_history import GAHistoryIntegrityError
from memory_agent.memory.read_context_predictive_memory_agent import (
    UNIFIED_SYSTEM, PUBLIC_FORECAST_REMINDER)
from memory_agent.memory.predictive_memory_agent import PHASE2_SYSTEM

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
CANDIDATE = 'pma_predictive_read_context_v1'


def load_definition(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    body = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec'), namespace)
    return namespace[name]


def test_actual_litellm_and_anthropic_translation(monkeypatch, tmp_path):
    from harbor.llms.lite_llm import LiteLLM
    from litellm.llms.anthropic.chat.transformation import AnthropicConfig
    from harbor.llms import lite_llm

    signed = [{'type': 'thinking', 'thinking': 'synthetic-private', 'signature': 'synthetic-signature'}]
    queue = iter([
        {'content': '', 'tool_calls': [call('memory_read', {'bank_id': 'knowledge'}, ident='r1')],
         'provider_specific_fields': {'thinking_blocks': signed}, 'reasoning_content': 'synthetic-private'},
        {'content': '', 'tool_calls': [call('memory_add', {'content': 'exact public text'}, 'a1')],
         'thinking_blocks': signed},
        {'content': '<no_intervention/>'}])
    wire, bodies = [], []

    async def completion(**kwargs):
        wire.append(copy.deepcopy(kwargs))
        bodies.append(AnthropicConfig().transform_request(
            model='claude-opus-4-8', messages=copy.deepcopy(kwargs['messages']),
            optional_params={'max_tokens': 1024, 'thinking': {'type': 'adaptive'}},
            litellm_params={}, headers={}))
        return {'choices': [{'message': next(queue), 'finish_reason': 'stop'}]}

    monkeypatch.setattr(lite_llm.litellm, 'acompletion', completion)
    llm = LiteLLM('anthropic/claude-opus-4-8', api_key='synthetic-not-a-key')
    agent = Agent(llm=llm)
    audit_namespace = {'copy': copy, 'json': json, 'os': os,
                       'time': __import__('time'), 'Path': Path,
                       'PMAAuditIntegrityError': type('AuditError', (BaseException,), {})}
    audit_namespace['append_private_audit'] = load_definition(
        STAGE / 'worker_main.py', 'append_private_audit', audit_namespace)
    install = load_definition(STAGE / 'worker_main.py', 'install_transport_audit', audit_namespace)
    install(SimpleNamespace(_memory_llm=llm, _memory_agent=agent,
                            _research_candidate=CANDIDATE), tmp_path)
    result = run(agent)
    assert len(wire) == 3 and len(result.operations) == 2
    reminded = UNIFIED_SYSTEM + '\n\n' + PUBLIC_FORECAST_REMINDER
    for body, expected in zip(bodies, [UNIFIED_SYSTEM, reminded, reminded]):
        assert "".join(block["text"] for block in body["system"]) == expected
    assert len(agent.memory.knowledge) == 1
    for index, expected in [(1, ['r1']), (2, ['r1', 'a1'])]:
        blocks = [b for m in bodies[index]['messages'] for b in m['content']]
        assert all(b.get('text') for b in blocks if b['type'] == 'text')
        assert [b['tool_use_id'] for b in blocks if b['type'] == 'tool_result'] == expected
        assert [b['id'] for b in blocks if b['type'] == 'tool_use'] == expected
        assert any(b.get('signature') == 'synthetic-signature' for b in blocks)
    assert all(request.get('tools') for request in wire)
    assert result.reasoning_phase1 is result.reasoning_phase2 is None
    audit = (tmp_path / 'memory_payload.jsonl').read_text()
    assert 'synthetic-signature' not in audit and 'synthetic-private' not in audit
    assert 'exact public text' in audit
    assert len((tmp_path / 'memory_transport.jsonl').read_text().splitlines()) == 3


def test_actual_episode_keeps_initial_and_eight_new_step_cadence(tmp_path):
    Episode = load_definition(STAGE / 'episode.py', 'PMAEpisode', {
        'Path': Path, 'asyncio': asyncio, 'json': json, 'hashlib': hashlib,
        'os': os, 'stable_initial_text': lambda value: value})
    llm = Script(response(), response(), response())
    memory_agent = Agent(llm=llm)

    class Host:
        # This regression intentionally covers the explicit eight-round mode.
        _sliding_window_size = 8
        _research_candidate = CANDIDATE
        _reset_status_on_episode = _reset_knowledge_on_episode = _reset_procedural_on_episode = False
        def __init__(self):
            self._memory_agent = memory_agent
            self._memory = memory_agent.memory
            self._trigger = SimpleNamespace(reset=lambda: None)
            self._accumulated_observations = []
        def _accumulate_step(self, *, step, observation):
            self._accumulated_observations.append({'step': step, 'observation': observation})
        def _format_step_entry(self, entry):
            return f"actor-step-{entry['step']}"
        async def _trigger_memory_agent(self, *, step_count):
            await self._memory_agent.process('P2 original task plus recent window', step_count)

    async def exercise():
        host = Host()
        episode = Episode(host, run_id='synthetic', task_id='synthetic', archive=tmp_path / 'archive')
        first = await episode._task_start({'initial_user_content': 'task EXACT <history>verbatim</history>'})
        assert first['trigger_reason'] == 'task_start'
        for i in range(1, 19):
            episode.last_attempt = i
            status = await episode._actor_step({'actor_attempt': i,
                'step_status': 'parse_error' if i == 3 else 'normal',
                'public_input': [], 'public_blocks': [], 'public_results': []})
            assert status['triggered'] == (i in (8, 16))
        assert episode.batch_steps == 2
    asyncio.run(exercise())
    assert len(llm.calls) == 3
    assert llm.calls[0]['prompt'] == '<task_description>\ntask EXACT <history>verbatim</history>\n</task_description>'
    assert llm.calls[1]['prompt'] == '<task_trajectory>\n' + '\n\n'.join(f'actor-step-{i}' for i in range(1, 9)) + '\n</task_trajectory>'
    assert llm.calls[2]['prompt'] == '<task_trajectory>\n' + '\n\n'.join(f'actor-step-{i}' for i in range(9, 17)) + '\n</task_trajectory>'


def test_candidate_registry_source_identity_and_actor_projection(monkeypatch):
    from experiment_runner.methods import resolve, candidate_names
    from experiment_runner import startup
    from pma_upstream_bridge import UpstreamPMAClient
    from importlib import import_module
    cert = import_module(startup.DRIVER + '.single_run_certification')
    method = resolve('pma-predictive-read-context')
    assert method.research_candidate == CANDIDATE and method.task_turns_max is None
    assert CANDIDATE in candidate_names('B')
    file = (STAGE / 'vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py').relative_to(ROOT).as_posix()
    assert file in cert.READ_CONTEXT_PREDICTIVE_SOURCE_FILES
    assert file not in cert.CONTEXT_PREDICTIVE_SOURCE_FILES
    monkeypatch.setattr(cert, '_committed_source_sha', lambda root, name: name)
    assert file in cert.source_identity(ROOT, predictive_read_context=True)
    assert file not in cert.source_identity(ROOT, predictive_context=True)
    seen = []
    client = object.__new__(UpstreamPMAClient)
    client.exchange = lambda kind, **fields: seen.append((kind, fields)) or {}
    monkeypatch.setenv('GA_PMA_UPSTREAM_CANDIDATE', CANDIDATE)
    blocks = [{'type': 'text', 'text': 'unredacted visible actor output'}]
    client.actor_step(8, status='normal', public_blocks=blocks, public_results=[], public_input='actual input')
    assert seen[0][1]['public_blocks'] is blocks
    assert seen[0][1]['public_input'] == 'actual input'


def test_read_only_repeated_read_and_duplicate_replay():
    a = Agent(llm=Script(response(call('memory_read', {'bank_id': 'knowledge'}, ident='one')),
        response(call('memory_read', {'bank_id': 'knowledge'}, ident='two')), response()))
    result = run(a)
    assert [o.action for o in result.operations] == ['read', 'read']
    assert not a.memory.knowledge and len(a.llm.calls) == 3
    a.llm = Script(response(call('memory_add', {'content': 'replay'}, 'one')))
    with pytest.raises(GAHistoryIntegrityError):
        run(a, 'next wake', 8)
    assert not a.memory.knowledge


def test_read_all_more_than_fifty_and_tool_failure(monkeypatch):
    a = Agent(llm=Script(response(call('memory_read', {'bank_id': 'knowledge'})), response()))
    for i in range(65):
        a.memory.save_knowledge(f'entry-{i}')
    result = run(a)
    assert 'entry-0' in result.operations[0].content
    assert 'entry-64' in result.operations[0].content
    a.llm = Script(response(call('memory_read', {'bank_id': 'knowledge'}, ident='failed-read')), response())
    original = a._format_memory_bank
    count = 0
    def fail_read(*args):
        nonlocal count
        count += 1
        if count == 1:
            raise OSError('synthetic read error')
        return original(*args)
    monkeypatch.setattr(a, '_format_memory_bank', fail_read)
    result = run(a, 'next trajectory', 8)
    assert not result.operations[0].success
    assert result.operations[0].error == 'synthetic read error'
    assert len(a.memory.knowledge) == 65


def test_cancelled_continuation_does_not_enter_p2():
    a = Agent(llm=Script(response(call('memory_read', {'bank_id': 'knowledge'})), asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        run(a)
    assert len(a.llm.calls) == 2 and all(c.get('tools') for c in a.llm.calls)


def test_unsupplied_context_and_changed_task_rejected():
    a = Agent(llm=Script())
    with pytest.raises(GAHistoryIntegrityError):
        asyncio.run(a.process('do not parse this into an original task', 1))
    a.set_phase1_context(task='one', trajectory='')
    with pytest.raises(GAHistoryIntegrityError):
        a.set_phase1_context(task='two', trajectory='')
    assert not a.llm.calls


@pytest.mark.parametrize('candidate,expected', [
    (CANDIDATE, 'RemindFirstMemoryAgent'),
    ('pma_predictive_context_v1', 'ContextPredictiveMemoryAgent'),
    ('pma_predictive_f838_v1', 'MemoryAgent'),
])
def test_actual_constructor_selects_independent_agent(tmp_path, candidate, expected):
    from memory_agent.memory.context_predictive_memory_agent import ContextPredictiveMemoryAgent
    from memory_agent.memory.universal_memory import UniversalMemory
    class Host:
        def __init__(self, **kwargs):
            self._llm = kwargs['llm']
            self._memory_llm = Script(response())
            self._memory = UniversalMemory()
            self._memory_agent = ContextPredictiveMemoryAgent(memory=self._memory)
    construct = load_definition(STAGE / 'episode.py', 'construct_upstream', {
        'MemoryEnabledTerminus2': Host, 'DisabledActorLLM': type('Disabled', (), {}),
        'Path': Path})
    host = construct(tmp_path, research_candidate=candidate)
    assert type(host._memory_agent).__name__ == expected
    assert host._memory_agent.memory is host._memory
    assert host._memory_agent.llm is host._memory_llm


def test_large_original_and_read_receipt_are_not_new_failure_limits():
    task = '<history>' + 'exact original requirement ' * 5000 + '</history>'
    bank = '<tool_result>' + 'exact saved information ' * 5000 + '</tool_result>'
    a = Agent(llm=Script(response(call('memory_read', {'bank_id': 'knowledge'})), response()))
    memory_id = a.memory.save_knowledge(bank)
    run(a, task=task)
    assert a.llm.calls[0]['prompt'] == '<task_description>\n' + task + '\n</task_description>'
    next_request = a.llm.calls[1]
    assert task in str(next_request)
    read = next(json.loads(m['content']) for m in next_request['message_history'] if m['role'] == 'tool')
    assert read['content'] == f'<memory_bank>\n[{memory_id}] {bank}\n</memory_bank>'
    assert len(a.llm.calls) == 2


def test_prior_history_uses_existing_ga_compression(monkeypatch):
    from memory_agent.memory import read_context_predictive_memory_agent as module
    from memory_agent.memory.ga_context_history import GAHistoryConfig
    original = module.trim_observer_history
    seen = []
    def trim(completed, protected, config, *, round_number):
        before = copy.deepcopy(protected)
        seen.append((copy.deepcopy(completed), before))
        result = original(completed, protected, config, round_number=round_number)
        assert protected == before  # Original task and this wake never enter compression.
        return result
    monkeypatch.setattr(module, 'trim_observer_history', trim)
    monkeypatch.setattr(GAHistoryConfig, 'cut_msg_interval', 1)
    old = '<history>OLD_TRAJECTORY_MUST_USE_GA_COMPRESSION</history>'
    replies = [response() for _ in range(10)]
    replies[2] = response(call('memory_add', {'content': 'native old payload'}, 'old-add'), content='<no_intervention/>')
    a = Agent(llm=Script(*replies))
    for i in range(10):
        run(a, old if i == 1 else f'fresh actor steps {i}', i,
            task='<history>original task must stay exact</history>')
    assert len(seen) == 10  # One shared loop protects each active wake.
    latest = str(a.llm.calls[-1])
    assert 'OLD_TRAJECTORY_MUST_USE_GA_COMPRESSION' not in latest
    assert '<history>[...]</history>' in latest
    assert '<history>original task must stay exact</history>' in latest
    assert 'fresh actor steps 9' in latest
    # The old GA leading-receipt sanitization is intentionally not used: the
    # native call and receipt remain linked while older visible text compresses.
    prior = a.llm.calls[-1]['message_history']
    calls = [item for message in prior for item in message.get('tool_calls', [])]
    receipts = [message for message in prior if message.get('role') == 'tool']
    assert [item['id'] for item in calls] == [item['tool_call_id'] for item in receipts] == ['old-add']
    assert json.loads(calls[0]['function']['arguments']) == {'content': 'native old payload'}
    assert json.loads(receipts[0]['content'])['success'] is True
