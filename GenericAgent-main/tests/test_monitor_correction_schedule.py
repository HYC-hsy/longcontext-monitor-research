import queue
import threading


from monitor_agent_core.correction_barrier import CorrectionBarrier
from monitor_agent_core.runtime import MonitorRuntime, _worker


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
        assert arrived.wait(3)
        assert gate.is_active()
        arrived.clear()
        send({'kind': 'intervention', 'message': 'first'})
        assert arrived.wait(3)
        assert gate.wait()
        assert order[:2] == ['stop', ('deliver', 'first', True)]
        arrived.clear()
        send({'kind': 'intervention', 'message': 'followup'})
        assert arrived.wait(3)
        assert ('deliver', 'followup', False) in order
        assert order.count('stop') == 1
        arrived.clear()
        send({'kind': 'review_silent'})
        send({'kind': 'review_wake', 'identity': 'c'})
        assert arrived.wait(3)
        assert gate.is_active() and order.count('stop') == 2
        send({'kind': 'failure', 'error': 'stream failed'})
        assert gate.wait()
    finally:
        runtime.close()
    assert not gate.is_active()


def test_worker_waits_for_host_before_first_model_and_releases_on_silence(tmp_path, monkeypatch):
    from monitor_agent_core.actions import MonitorAction
    calls = []
    class Client:
        def __init__(self, *args): pass
    class Monitor:
        def __init__(self, *args): pass
        def review(self, *args, **kwargs):
            calls.append('model')
            return MonitorAction('wait', {'after_turns': 1})
    monkeypatch.setattr('monitor_agent_core.provider.MonitorProviderClient', Client)
    monkeypatch.setattr('monitor_agent_core.agent.MonitorAgent', Monitor)
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    commands, outputs, acknowledgments = queue.Queue(), queue.Queue(), queue.Queue()
    stop = threading.Event()
    cfg = dict(config_name='fixture', model_config={}, evidence_root=evidence,
               private_root=tmp_path / 'private', task_workspace=tmp_path,
               task_original_path='original', max_review_turns=20,
               wake_receipts=acknowledgments, stop_event=stop)
    thread = threading.Thread(target=_worker, args=(cfg, commands, outputs))
    thread.start()
    try:
        wake = outputs.get(timeout=2)
        assert wake['kind'] == 'review_wake' and not calls
        acknowledgments.put({'identity': wake['identity'], 'accepted': True})
        assert outputs.get(timeout=2)['kind'] == 'review_silent'
        assert calls == ['model']
        assert outputs.get(timeout=2)['kind'] == 'ready'
        commands.put({'kind': 'boundary', 'cursor': 2, 'task_turn': 1})
        wake = outputs.get(timeout=2)
        assert wake['kind'] == 'review_wake' and len(calls) == 1
        acknowledgments.put({'identity': wake['identity'], 'accepted': True})
        assert outputs.get(timeout=2)['kind'] == 'review_silent'
        assert len(calls) == 2
    finally:
        stop.set()
        commands.put({'kind': 'close'})
        thread.join(3)
    assert not thread.is_alive()


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

