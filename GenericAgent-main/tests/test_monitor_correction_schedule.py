import ast
import inspect
import json
import threading
from pathlib import Path

import pytest

from monitor_agent_core.correction_barrier import CorrectionBarrier
from monitor_agent_core.provider import MonitorProviderClient, ProviderError
from monitor_agent_core.runtime import MonitorRuntime
from monitor_agent_core.vendor.liveplan_blocking import BlockingDecision
from test_monitor_provider import config


def forwarding_worker(config, commands, outputs):
    while True:
        value = commands.get()
        if value['kind'] == 'close':
            return
        outputs.put(value)


def test_first_stop_then_parallel_followup_and_next_episode(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    order = []
    arrived = threading.Event()
    gate = CorrectionBarrier()
    def begin(identity):
        gate.begin(identity)
        order.append('stop')
        arrived.set()
    def deliver(message):
        order.append(('deliver', message, gate.is_active()))
        arrived.set()
    def end(identity):
        gate.end(identity)
    runtime = MonitorRuntime(public_task='Task', task_workspace=workspace,
        artifact_dir=tmp_path / 'artifacts', config_name='fixture', model_config={},
        interrupt_callback=deliver, correction_begin=begin, correction_end=end,
        worker_target=forwarding_worker)
    def send(value):
        runtime._commands.put(value)
    try:
        send({'kind': 'correction_begin', 'identity': 'a'})
        assert arrived.wait(3)
        assert gate.is_active()
        arrived.clear()
        send({'kind': 'intervention', 'message': 'first'})
        assert arrived.wait(3)
        assert gate.wait()
        assert order[:2] == ['stop', ('deliver', 'first', True)]
        arrived.clear()
        send({'kind': 'correction_begin', 'identity': 'b'})
        send({'kind': 'intervention', 'message': 'followup'})
        assert arrived.wait(3)
        assert ('deliver', 'followup', False) in order
        assert order.count('stop') == 1
        arrived.clear()
        send({'kind': 'review_silent'})
        send({'kind': 'correction_begin', 'identity': 'c'})
        assert arrived.wait(3)
        assert gate.is_active() and order.count('stop') == 2
        send({'kind': 'failure', 'error': 'stream failed'})
        assert gate.wait()
    finally:
        runtime.close()
    assert not gate.is_active()


def test_stream_stops_before_arguments_and_failure_releases(monkeypatch):
    client = MonitorProviderClient('openai', config('fixture'))
    events = []
    client.correction_event = lambda kind, identity: events.append((kind, identity))
    def lines():
        yield 'data: ' + json.dumps({'type': 'response.output_item.added',
            'output_index': 0, 'item': {'type': 'function_call', 'name': 'intervene',
                                     'call_id': 'x', 'id': 'fc-x', 'arguments': ''}})
        assert events[0][0] == 'begin'  # before any correction text exists
        raise ProviderError('test stream failure')
    monkeypatch.setattr(client, '_request_with_recovery',
                        lambda _: client._parse_openai_responses(lines()))
    with pytest.raises(ProviderError, match='test stream failure'):
        client._request([])
    assert [e[0] for e in events] == ['begin', 'end']
    assert events[0][1] == events[1][1]


def test_only_explicit_tool_choice_signals_stop():
    client = MonitorProviderClient('openai', config('fixture'))
    events = []
    client.correction_event = lambda *args: events.append(args)
    for name in ['file_read', 'wait', 'review_context', 'maybe intervene', 'allow_complete']:
        client._announce_correction(name)
    assert not events
    client._announce_correction('intervene')
    client._announce_correction('intervene')
    assert len(events) == 1


def test_stale_release_cannot_release_new_correction():
    gate = CorrectionBarrier()
    gate.begin('new')
    gate.end('old')
    assert gate.is_active()
    gate.end('new')
    assert gate.wait()


def test_crashed_owner_cannot_leave_permanent_barrier():
    gate = CorrectionBarrier()
    gate.begin('lost', timeout=.02)
    assert gate.wait()
    assert not gate.is_active()


def test_user_stop_breaks_delivery_wait():
    gate = CorrectionBarrier()
    gate.begin('pending')
    assert not gate.wait(lambda: True)
    gate.end()


def test_task_loop_waits_only_for_announced_correction():
    from test_task_interruption import Parent, Handler, InterruptThenContinueClient
    from agent_loop import agent_runner_loop, exhaust
    parent = Parent()
    gate = CorrectionBarrier()
    parent.wait_monitor_correction = gate.wait
    client = InterruptThenContinueClient(parent)
    gate.begin('first')
    results = []
    thread = threading.Thread(target=lambda: results.append(exhaust(agent_runner_loop(
        client, 'system', 'task', Handler(parent), [], max_turns=3, verbose=False))))
    thread.start()
    try:
        assert client.calls == []
        gate.end('first')
        thread.join(3)
        assert not thread.is_alive() and results[0]['result'] == 'EXITED'
    finally:
        gate.end()
        thread.join(3)


def test_upstream_blocking_method_body_is_unchanged():
    root = Path(__file__).resolve().parents[2]
    source = root / ('some_research/research_library/05_safety_and_monitoring/repositories/'
                     'Intelligent-CAT-Lab__Agent-Planner/plan_monitor/phases.py')
    tree = ast.parse(source.read_text(encoding='utf-8'))
    original = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                    and n.name == 'should_block_and_refine')
    local = ast.parse(inspect.getsource(__import__(
        'monitor_agent_core.vendor.liveplan_blocking', fromlist=['BlockingDecision'])))
    copied = next(n for n in ast.walk(local) if isinstance(n, ast.FunctionDef)
                  and n.name == 'should_block_and_refine')
    assert ast.dump(original) == ast.dump(copied)
