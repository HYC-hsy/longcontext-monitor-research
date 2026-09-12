import threading
import time

import pytest

from monitor_agent_core.runtime import MonitorRuntime
from monitor_agent_core.pause_lease import PauseLease
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def hybrid_worker(config, commands, outputs):
    outputs.put({'kind': 'task_control', 'operation': 'pause', 'reason': 'questionable premise', 'seconds': 2})
    while True:
        command = commands.get()
        if command['kind'] == 'close':
            return
        outputs.put({'kind': 'intervention', 'message': 'Compare the original test expectation.', 'cursor': 1})


def test_concurrent_archive_pause_and_correction_resumption(tmp_path):
    lease = PauseLease()
    paused, delivered = threading.Event(), threading.Event()
    def pause(reason, seconds):
        result = lease.request(reason, seconds)
        paused.set()
        return result
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    runtime = MonitorRuntime(public_task='Task', task_workspace=workspace,
        artifact_dir=tmp_path / 'artifacts', config_name='fixture',
        model_config={'monitor_hybrid_control': True},
        interrupt_callback=lambda message: delivered.set(),
        pause_callback=pause, resume_callback=lease.release, worker_target=hybrid_worker)
    try:
        assert paused.wait(4)
        advanced = threading.Event()
        thread = threading.Thread(target=lambda: (lease.wait(), advanced.set()))
        thread.start()
        assert not advanced.wait(.03)
        started = time.monotonic()
        runtime.archive_boundary({'internal_turn': 1, 'response_content': 'public intent'})
        assert time.monotonic() - started < .2
        assert delivered.wait(2)
        assert advanced.wait(1)
        thread.join()
    finally:
        runtime.close()
    assert lease.wait()


def test_hybrid_requires_real_host_capability(tmp_path):
    with pytest.raises(ValueError, match='requires host'):
        MonitorRuntime(public_task='Task', task_workspace=tmp_path / 'workspace',
            artifact_dir=tmp_path / 'artifacts', config_name='fixture',
            model_config={'monitor_hybrid_control': True}, interrupt_callback=lambda _: None)


def test_tool_validation_and_no_root_pause(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    client = MonitorProviderClient('openai', {'apikey': 'fixture', 'apibase': 'https://example.test',
                                           'monitor_hybrid_control': True})
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))
    operations = []
    monitor.task_control_callback = lambda op, **kw: operations.append((op, kw)) or {'status': 'queued'}
    assert monitor.dispatch('task_control', {'operation': 'pause', 'reason': 'concrete risk'}).data['status'] == 'queued'
    assert monitor.dispatch('task_control', {'operation': 'resume'}).data['status'] == 'queued'
    assert len(operations) == 2
    assert monitor.dispatch('task_control', {'operation': 'pause', 'reason': ''}).data['status'] == 'error'
    monitor.completion_pending = True
    assert monitor.dispatch('task_control', {'operation': 'pause'}).data['status'] == 'already_waiting'
    assert len(operations) == 2


def test_real_agent_loop_obeys_pause_before_call_and_receives_correction():
    from test_task_interruption import Parent, Handler, InterruptThenContinueClient
    from agent_loop import agent_runner_loop, exhaust
    parent = Parent()
    lease = PauseLease()
    parent.wait_monitor_pause = lease.wait
    handler = Handler(parent)
    client = InterruptThenContinueClient(parent)
    lease.request('inspect the basis', 2)
    results = []
    thread = threading.Thread(target=lambda: results.append(exhaust(agent_runner_loop(
        client, 'system', 'original task', handler, [], max_turns=3, verbose=False))))
    thread.start()
    try:
        time.sleep(.03)
        assert client.calls == []
        lease.release()
        thread.join(2)
        assert not thread.is_alive()
        assert results[0]['result'] == 'EXITED'
        assert 'literal wildcard' in client.calls[-1][-1]['content']
    finally:
        lease.release()
        thread.join(1)
