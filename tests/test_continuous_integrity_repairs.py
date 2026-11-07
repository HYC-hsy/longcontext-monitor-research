"""Both continuous variants: failures, telemetry and input-neutral provenance."""
import ast
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from types import SimpleNamespace

import pytest

from memory_agent.memory.context_predictive_memory_agent import (
    ContextPredictiveMemoryAgent, PMAPhaseError)
from memory_agent.memory.read_context_predictive_memory_agent import ReadContextPredictiveMemoryAgent
from memory_agent.memory.predictive_memory_agent import MemoryAgent as HistoricalAgent
ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'


def response(*calls, content=''):
    return SimpleNamespace(content=content, tool_calls=list(calls))


def call(name, arguments):
    return {'id': 'fixture-call', 'function': {'name': name, 'arguments': arguments}}


def load_definition(path, name, namespace):
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name == name)
    body = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node]
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), 'exec'), namespace)
    return namespace[name]


VARIANTS = [ContextPredictiveMemoryAgent, ReadContextPredictiveMemoryAgent]


class Script:
    def __init__(self, replies):
        self.replies, self.calls = iter(replies), []

    async def call(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        reply = next(self.replies)
        if isinstance(reply, BaseException):
            raise reply
        return reply


def prepare(cls, replies):
    agent = cls(llm=Script(replies))
    if isinstance(agent, ReadContextPredictiveMemoryAgent):
        agent.set_phase1_context(task='EXACT task', trajectory='')
    return agent


@pytest.mark.parametrize('cls', VARIANTS)
@pytest.mark.parametrize('phase', ['P1', 'P2'])
def test_failed_phase_crosses_actual_host_silence_handler(cls, phase):
    failure = RuntimeError('synthetic confidential error detail')
    replies = [failure] if phase == 'P1' else [response(), failure]
    agent = prepare(cls, replies)
    Host = load_definition(STAGE / 'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py',
        'MemoryEnabledTerminus2', {'Terminus2': object})
    host = Host.__new__(Host)
    host._memory_agent, host._memory_trigger_count = agent, 0
    host._memory_step_in_episode = host._memory_operation_count = host._noop_count = 0
    host._get_memory_agent_context = lambda: 'EXACT observation'
    records = []
    host._record_memory_step = lambda **kwargs: records.append(kwargs)
    with pytest.raises(PMAPhaseError) as caught:
        asyncio.run(host._trigger_memory_agent(step_count=1))
    assert caught.value.phase == phase
    assert caught.value.error_type == 'RuntimeError'
    assert caught.value.__cause__ is failure
    assert 'confidential' not in str(caught.value)
    assert not records and host._noop_count == 0
    assert len(agent.llm.calls) == (1 if phase == 'P1' else 2)


@pytest.mark.parametrize('cls', VARIANTS)
@pytest.mark.parametrize('phase', ['P1', 'P2'])
def test_cancellation_is_not_a_decision(cls, phase):
    cancel = asyncio.CancelledError()
    agent = prepare(cls, [cancel] if phase == 'P1' else [response(), cancel])
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(agent.process('original observation'))
    assert len(agent.llm.calls) == (1 if phase == 'P1' else 2)


@pytest.mark.parametrize('cls', VARIANTS)
@pytest.mark.parametrize('method,phase', [('_build_phase1_prompt', 'P1'),
    ('_execute_tool_calls', 'P1'), ('_build_phase2_prompt', 'P2'),
    ('_parse_phase2_response', 'P2')])
def test_prompt_operation_and_parser_errors_do_not_become_noop(cls, method, phase):
    agent = prepare(cls, [response(), response(content='<no_intervention/>')])
    def fail(*args):
        raise ValueError('synthetic')
    setattr(agent, method, fail)
    with pytest.raises(PMAPhaseError) as caught:
        asyncio.run(agent.process('observation'))
    assert caught.value.phase == phase


@pytest.mark.parametrize('cls', VARIANTS)
@pytest.mark.parametrize('decision', ['<no_intervention/>', '<context_for_action>Exact reminder.</context_for_action>'])
def test_successful_phase_outputs_and_original_prompts_preserved(cls, decision):
    replies = [response(call('memory_add', {'content': 'EXACT bank'})), response(content=decision)]
    agent = prepare(cls, replies)
    result = asyncio.run(agent.process('EXACT observation', 8))
    assert len(result.operations) == 1 and result.operations[0].success
    assert result.should_inject == ('context_for_action' in decision)
    assert result.reasoning_phase1 is result.reasoning_phase2 is None
    assert result.user_prompt_phase2 == HistoricalAgent._build_phase2_prompt(agent, 'EXACT observation', 8)
    if cls is ContextPredictiveMemoryAgent:
        empty = HistoricalAgent()
        assert result.user_prompt_phase1 == empty._build_phase1_prompt('EXACT observation', 8)
    else:
        assert result.user_prompt_phase1 == '[Task Description]\nEXACT task'


def definitions(path, names, namespace):
    tree = ast.parse(path.read_text())
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), namespace)
    return namespace


def trimmer(path, observing=True):
    events = []
    digest = lambda x: hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()
    ns = {'json': json, 're': re, '_telemetry_enabled': lambda: observing,
          '_research_id': lambda _: 'test-transform', '_sha256_json': digest,
          '_session_research_emit': lambda sess, event, data, **kw: events.append((event, data, kw)),
          '_research_emit': lambda event, data, **kw: events.append((event, data, kw))}
    definitions(path, ['compress_history_tags', '_sanitize_leading_user_msg', 'trim_messages_history'], ns)
    return ns, events


@pytest.mark.parametrize('host_copy', [False, True])
@pytest.mark.parametrize('case', ['periodic', 'noop', 'forced', 'prune'])
def test_compression_telemetry_reports_actual_history_on_all_exits(host_copy, case):
    path = (STAGE / 'vendor/pma_89e5c0d/src/memory_agent/memory/ga_context_history.py'
            if host_copy else ROOT / 'GenericAgent-main/llmcore.py')
    ns, events = trimmer(path)
    history = [{'role': 'user' if i % 2 == 0 else 'assistant', 'content': [
        {'type': 'text', 'text': '<history>' + 'x' * 3000 + '</history>' if i == 0 else 'short'}]}
        for i in range(13)]
    if case == 'prune':
        for item in history:
            item['content'][0]['text'] = 'x' * 1000
    ns['compress_history_tags']._cd = 4 if case == 'periodic' else 0
    before = copy.deepcopy(history)
    cap = 30000 if case in ('periodic', 'noop') else 500
    ns['trim_messages_history'](history, SimpleNamespace(context_win=cap))
    assert len(events) == 2
    assert events[0][2] == events[1][2] == {'history_transform_id': 'test-transform'}
    after = events[-1][1]
    assert after['message_count'] == len(history)
    assert after['bytes'] == sum(len(json.dumps(m, ensure_ascii=False)) for m in history)
    assert after['sha256'] == ns['_sha256_json'](history)
    assert after['changed'] == (history != before) == (case != 'noop')
    # Telemetry must not affect trimming or compression counters.
    quiet, _ = trimmer(path, observing=False)
    quiet['compress_history_tags']._cd = 4 if case == 'periodic' else 0
    quiet['trim_messages_history'](before, SimpleNamespace(context_win=cap))
    assert before == history


def ask_fixture(blocks, source=None):
    source = source or ROOT / 'GenericAgent-main/llmcore.py'
    ns = {'json': json, 'copy': copy, 're': re,
          'trim_messages_history': lambda *_: None, '_parse_text_tool_calls': lambda text: ([], text)}
    definitions(source, ['MockFunction', 'MockToolCall', 'MockResponse', '_ensure_text_block',
                         '_public_response_blocks', '_public_response_provenance'], ns)
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeClaudeSession')
    ask = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'ask')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ask], type_ignores=[])), str(source), 'exec'), ns)
    def raw_ask(messages):
        if False:
            yield None
        return copy.deepcopy(blocks)
    sess = SimpleNamespace(lock=threading.Lock(), history=[], raw_ask=raw_ask)
    gen, visible = ns['ask'](sess, {'role': 'user', 'content': [{'type': 'text', 'text': 'task'}]}), []
    while True:
        try:
            visible.append(next(gen))
        except StopIteration as done:
            return done.value, sess.history, visible


@pytest.mark.parametrize('native_text', [False, True])
def test_summary_provenance_never_changes_actor_history_or_observer_text(native_text):
    blocks = [{'type': 'thinking', 'thinking': 'SYNTHETIC first line\nUNEXPOSED later line',
               'signature': 'SYNTHETIC signature'},
              {'type': 'tool_use', 'id': 'tool-1', 'name': 'shell', 'input': {'cmd': 'true'}}]
    if native_text:
        blocks.insert(1, {'type': 'text', 'text': '<summary>Native literal text</summary>'})
    actual, history, visible = ask_fixture(blocks)
    # The original implementation is reconstructed by removing only new metadata.
    source = (ROOT / 'GenericAgent-main/llmcore.py').read_text()
    source = source.replace('        response.public_blocks_provenance = _public_response_provenance(content_blocks, bool(_injected))\n', '')
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        original = Path(directory) / 'original.py'
        original.write_text(source)
        old, old_history, old_visible = ask_fixture(blocks, original)
    assert (history, visible, actual.public_blocks, actual.content) == (
        old_history, old_visible, old.public_blocks, old.content)
    meta = actual.public_blocks_provenance
    assert meta['visibility_scope'] == 'ga_visible_postprocessed'
    assert [row['origin'] for row in meta['blocks']] == [
        'provider_native' if native_text else 'ga_synthetic_summary', 'provider_native']
    assert ('UNEXPOSED' not in json.dumps(meta) and 'signature' not in json.dumps(meta))
    assert 'ga_synthetic_summary' not in json.dumps(history)
    # public_blocks remains the same projection as the actual assistant history.
    assert actual.public_blocks == [b for b in history[-1]['content'] if b['type'] != 'thinking']


@pytest.mark.parametrize('candidate', ['pma_predictive_context_v1', 'pma_predictive_read_context_v1'])
def test_provenance_is_archived_but_not_added_to_pma_prompt(monkeypatch, tmp_path, candidate):
    from pma_upstream_bridge import UpstreamPMAClient
    MemoryEnabledTerminus2 = load_definition(
        STAGE / 'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py',
        'MemoryEnabledTerminus2', {'Terminus2': object, 'json': json})
    Episode = load_definition(STAGE / 'episode.py', 'PMAEpisode',
        {'Path': Path, 'asyncio': asyncio, 'json': json, 'hashlib': hashlib, 'os': os})
    result, _, _ = ask_fixture([{'type': 'thinking', 'thinking': 'synthetic summary'}])
    events = []
    client = UpstreamPMAClient.__new__(UpstreamPMAClient)
    client.exchange = lambda kind, **fields: events.append({'kind': kind, **fields}) or {}
    monkeypatch.setenv('GA_PMA_UPSTREAM_CANDIDATE', candidate)
    client.actor_step(1, status='normal', public_blocks=result.public_blocks, public_results=[],
        public_input=[], public_blocks_provenance=result.public_blocks_provenance)
    host = SimpleNamespace(_accumulated_observations=[], _research_candidate=candidate,
                           _memory_agent=SimpleNamespace())
    episode = Episode(host, run_id='r', task_id='t', archive=tmp_path / 'audit')
    asyncio.run(episode._predictive_actor_step(events[0], 1, 'normal'))
    episode._record(events[0], {'status': 'observed'})
    saved = json.loads((episode.archive / 'events.jsonl').read_text())
    assert saved['event']['public_blocks_provenance'] == result.public_blocks_provenance
    entry = host._accumulated_observations[0]
    assert 'public_blocks_provenance' not in entry
    formatted = MemoryEnabledTerminus2._format_step_entry(entry)
    assert result.public_blocks[0]['text'] in formatted
    assert 'ga_synthetic_summary' not in formatted and 'source_kind' not in formatted


@pytest.mark.parametrize('cls', VARIANTS)
@pytest.mark.parametrize('phase', ['P1', 'P2'])
def test_dispatcher_persists_safe_failure_then_worker_stops(cls, phase, tmp_path):
    from event_spool import EventDispatcher
    from pma_upstream_bridge import UpstreamPMAClient, PMABridgeError
    agent = prepare(cls, [RuntimeError('SECRET fixture')] if phase == 'P1'
                    else [response(), RuntimeError('SECRET fixture')])
    requests, responses = [tmp_path / 'spool' / name for name in ('requests', 'responses')]
    archive = tmp_path / 'archive'
    for path in (requests, responses, archive):
        path.mkdir(parents=True)
    async def handle(request):
        return await agent.process('original task observation')
    episode = SimpleNamespace(run_id='r', task_id='t', archive=archive, handle=handle)
    # Exchange is synchronous, so issue it on a thread while real dispatcher runs.
    client = UpstreamPMAClient(run_id='r', task_id='t', requests=requests,
                               responses=responses, deadline='uncapped')
    dispatcher = EventDispatcher(episode, requests, responses)
    async def exercise():
        waiting = asyncio.create_task(asyncio.to_thread(client.exchange, 'task_start'))
        try:
            for _ in range(200):
                if list(requests.glob('*.json')):
                    break
                await asyncio.sleep(.005)
            with pytest.raises(PMAPhaseError) as caught:
                await dispatcher.serve_once()
            with pytest.raises(PMABridgeError):
                await asyncio.wait_for(waiting, 2)
            return caught.value
        finally:
            # A failed assertion must not strand the thread's uncapped wait.
            client.deadline = time.time() - 1
    error = asyncio.run(exercise())
    assert error.phase == phase
    receipt = next(responses.glob('*.json')).read_text()
    assert json.loads(receipt)['status'] == 'error' and 'SECRET' not in receipt
    assert asyncio.run(dispatcher.serve_once()) == 0  # No replay of accepted failure.


@pytest.mark.parametrize('phase', ['P1', 'P2'])
def test_worker_records_failure_phase_without_error_text(phase, tmp_path):
    import time
    tree = ast.parse((STAGE / 'worker_main.py').read_text())
    serve = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'serve')
    start = next(i for i, n in enumerate(serve.body) if isinstance(n, ast.Assign)
                 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'reason')
    serve.body = serve.body[start:]
    error = PMAPhaseError(phase, RuntimeError('SECRET diagnostic'))
    async def fail():
        raise error
    scope = {'asyncio': asyncio, 'time': time, 'json': json, 'argparse': SimpleNamespace(Namespace=object),
             'stopped': asyncio.Event(), 'private': tmp_path,
             'episode': SimpleNamespace(ended=False, finalize_without_event=lambda reason: {'saved': True}),
             'dispatcher': SimpleNamespace(serve_once=fail)}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[serve], type_ignores=[])), 'worker_main.py', 'exec'), scope)
    with pytest.raises(PMAPhaseError):
        asyncio.run(scope['serve'](SimpleNamespace(deadline_epoch=None, run_id='r', task_id='t')))
    text = (tmp_path / 'worker_exit.json').read_text()
    data = json.loads(text)
    assert not data['task_end_saved'] and data['reason'] == 'worker_error:PMAPhaseError'
    assert data['failure'] == {'phase': phase, 'error_type': 'PMAPhaseError',
                               'cause_type': 'RuntimeError', 'decision_produced': False}
    assert 'SECRET' not in text


def test_both_method_source_identities_bind_every_repaired_runtime_file():
    from experiment_runner import startup
    from importlib import import_module
    cert = import_module(startup.DRIVER + '.single_run_certification')
    common = ['GenericAgent-main/llmcore.py', 'GenericAgent-main/agent_loop.py',
              'GenericAgent-main/pma_upstream_bridge.py']
    common += [(STAGE.relative_to(ROOT) / path).as_posix() for path in [
        'event_spool.py', 'worker_main.py', 'single_run_certification.py',
        'vendor/pma_89e5c0d/src/memory_agent/memory/ga_context_history.py',
        'vendor/pma_89e5c0d/src/memory_agent/memory/context_predictive_memory_agent.py']]
    for files in (cert.CONTEXT_PREDICTIVE_SOURCE_FILES, cert.READ_CONTEXT_PREDICTIVE_SOURCE_FILES):
        assert set(common) <= set(files)
    assert set(cert.READ_CONTEXT_PREDICTIVE_SOURCE_FILES) - set(cert.CONTEXT_PREDICTIVE_SOURCE_FILES) == {
        (STAGE.relative_to(ROOT) / 'vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py').as_posix()}
