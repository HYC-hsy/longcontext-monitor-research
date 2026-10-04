"""Zero-network routing checks for the opt-in root decision frame."""

import json
import multiprocessing as mp
import queue
import threading
import time

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.root_scope_v1 import ROOT_SYSTEM_PROMPT, task_budget_view
from monitor_agent_core.workspace import MonitorWorkspace
from monitor_agent_core.runtime import _worker


def make_monitor(tmp_path, mode):
    evidence = tmp_path / 'evidence'
    evidence.mkdir(parents=True)
    (evidence / 'original_task.txt').write_text('Complete the public behavior.\n', encoding='utf-8')
    (evidence / 'public_events.jsonl').write_text(json.dumps({
        'archive_sequence': 1, 'task_turn': 1, 'boundary': 'task_control_handoff',
        'text': 'Work is ready for review.', 'tool_calls': [], 'tool_results': []}) + '\n',
        encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private')
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_dcec': True, 'monitor_path_control_v0': True,
        'monitor_root_scope_v1': mode, 'monitor_dcec_working_chars': 4000,
    })
    monitor = MonitorAgent(client, workspace)
    current = {'generation': 1, 'request_id': 'completion-1', 'cursor': 1}
    monitor.completion_state = lambda: current
    return monitor, client, workspace, current


@pytest.mark.parametrize('mode', ['retained', 'isolated'])
def test_real_root_request_assembly_separates_history_and_working(tmp_path, monkeypatch, mode):
    monitor, client, workspace, handoff = make_monitor(tmp_path, mode)
    workspace.write_text('monitor/working.md', 'Old local judgment.')
    client.history.append({'role': 'user', 'content': [{'type': 'text', 'text': 'Old local History.'}]})
    captured = []

    def offline(tools):
        captured.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': 'allow', 'name': 'allow_complete', 'input': {}}], {})

    monkeypatch.setattr(client, '_request_once', offline)
    action = monitor.review('Root wake', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete'
    assert action.payload == {'request_id': 'completion-1', 'root_frame_generation': 1}
    request = captured[0]
    assert ROOT_SYSTEM_PROMPT in request['system']
    assert 'Recent public Task events' not in json.dumps(request)
    assert 'Complete the public behavior.' in json.dumps(request)
    visible = json.dumps(request)
    assert ('Old local History.' in visible) == (mode == 'retained')
    assert ('Old local judgment.' in visible) == (mode == 'retained')
    assert client.history[0]['content'][0]['text'] == 'Old local History.'
    assert (workspace.private_root / 'working.md').read_text() == 'Old local judgment.'
    assert (workspace.private_root / 'audit/root_frames/1/history.json').is_file()


def test_local_allow_blocked_and_mid_review_routes_before_next_request(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = make_monitor(tmp_path, 'isolated')
    active = [None]
    monitor.completion_state = lambda: active[0]
    captured = []

    def offline(tools):
        captured.append(client.assembled_request_snapshot(tools))
        active[0] = handoff
        return ([{'type': 'tool_use', 'id': 'allow', 'name': 'allow_complete', 'input': {}}], {})

    monkeypatch.setattr(client, '_request_once', offline)
    action = monitor.review('Ordinary wake')
    assert action.kind == 'root_route'
    assert action.payload['prior_model_turns'] == 1
    assert len(captured) == 1
    assert monitor.frame_kind == 'local'
    dialogue = (workspace.private_root / 'audit/dialogue.jsonl').read_text(encoding='utf-8')
    assert 'Only the current root decision frame' in dialogue


def test_root_intervention_invalidates_old_allow_and_preserves_local_state(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = make_monitor(tmp_path, 'retained')
    workspace.write_text('monitor/working.md', 'Persistent local note.')
    receipts = []
    monitor.intervention_callback = lambda message: receipts.append(message) or {'delivery': 'queued'}
    monkeypatch.setattr(client, '_request_once', lambda tools: (
        [{'type': 'tool_use', 'id': 'correct', 'name': 'intervene',
          'input': {'message': 'Please check the route behavior.'}}], {}))
    action = monitor.review('Root wake', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'root_intervened'
    assert receipts == ['Please check the route behavior.']
    assert monitor._intervened_generation == 1
    assert workspace.resolve_read('monitor/working.md').read_text() == 'Persistent local note.'
    assert monitor.dispatch('allow_complete', {}).data['status'] == 'error'


def test_root_note_write_and_tool_history_stay_inside_root_frame(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = make_monitor(tmp_path, 'isolated')
    workspace.write_text('monitor/working.md', 'Local note must remain.')
    calls = []

    def offline(tools):
        calls.append(client.assembled_request_snapshot(tools))
        if len(calls) == 1:
            return ([{'type': 'tool_use', 'id': 'note', 'name': 'file_write',
                      'input': {'path': 'monitor/working.md', 'content': 'Root note.'}}], {})
        return ([{'type': 'tool_use', 'id': 'allow', 'name': 'allow_complete', 'input': {}}], {})

    monkeypatch.setattr(client, '_request_once', offline)
    assert monitor.review('Root wake', completion_pending=True, root_handoff=handoff).kind == 'allow_complete'
    assert len(calls) == 2
    assert 'Root note.' in json.dumps(calls[1])
    assert 'note' in json.dumps(calls[1]['messages'])
    assert workspace.resolve_read('monitor/working.md').read_text() == 'Local note must remain.'
    assert (workspace.private_root / 'root_working/1.md').read_text() == 'Root note.'


def test_default_off_rejects_root_mode_without_path_control(tmp_path):
    monitor, client, workspace, handoff = make_monitor(tmp_path, 'off')
    assert monitor.root_scope_v1 == 'off'
    assert monitor.frame_kind == 'local'
    assert workspace.working_note_target == 'working.md'


@pytest.mark.parametrize('mode', ['retained', 'isolated'])
def test_task_turn_budget_in_ordinary_and_root_provider_requests(tmp_path, monkeypatch, mode):
    monitor, client, workspace, handoff = make_monitor(tmp_path, mode)
    used = [179]
    monitor.task_budget_state = lambda: (used[0], 180)
    client.recovery_deadline = time.monotonic() + 90
    client.recovery_stop = threading.Event()
    requests = []

    def offline(tools):
        requests.append(client.assembled_request_snapshot(tools))
        name = 'allow_complete' if client.observed_root_handoff else 'wait'
        arguments = {} if name == 'allow_complete' else {'after_turns': 1}
        return ([{'type': 'tool_use', 'id': name, 'name': name, 'input': arguments}], {})

    monkeypatch.setattr(client, '_request_once', offline)
    monitor.completion_state = lambda: None
    assert monitor.review('Ordinary wake').kind == 'wait'
    assert 'Task turns used: 179; limit: 180; remaining: 1.' in json.dumps(requests[-1])
    assert 'Remaining shared run time:' in json.dumps(requests[-1])
    used[0] = 180
    monitor.completion_state = lambda: handoff
    assert monitor.review('Root wake', completion_pending=True, root_handoff=handoff).kind == 'allow_complete'
    assert 'Task turns used: 180; limit: 180; remaining: 0.' in json.dumps(requests[-1])
    assert 'Remaining shared run time:' in json.dumps(requests[-1])


def test_task_turn_budget_unknown_is_not_inferred_from_public_event_turn():
    assert task_budget_view(None, 180, 12).startswith(
        'Task turns used: unknown; limit: 180; remaining: unknown.')
    assert task_budget_view(179, None, None).startswith(
        'Task turns used: 179; limit: unknown; remaining: unknown.')


def test_runtime_root_dispatch_uses_actual_frame_and_handoff(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = make_monitor(tmp_path, 'retained')
    task_workspace = tmp_path / 'task_workspace'
    task_workspace.mkdir()
    (task_workspace / 'app.py').write_text('print(1)\n', encoding='utf-8')
    requests = []

    def offline(self, tools):
        requests.append(self.assembled_request_snapshot(tools))
        name = 'allow_complete' if self.observed_root_handoff else 'wait'
        arguments = {} if name == 'allow_complete' else {'after_turns': 1}
        return ([{'type': 'tool_use', 'id': f'{name}-{len(requests)}',
                  'name': name, 'input': arguments}], {})

    monkeypatch.setattr(MonitorProviderClient, '_request_once', offline)
    commands, outputs, receipts = queue.Queue(), queue.Queue(), queue.Queue()
    stopped = threading.Event()
    active, cursor, latest = mp.Value('q', 0), mp.Value('q', 1), mp.Value('q', 1)
    task_budget_turns_used = mp.Value('q', 179)
    config = {
        'config_name': 'anthropic', 'model_config': client.config,
        'task_id': 'offline-task', 'evidence_root': str(workspace.evidence_root),
        'private_root': str(workspace.private_root), 'task_workspace': str(task_workspace),
        'max_review_turns': 4, 'task_original_path': None,
        'active_completion': active, 'completion_cursor': cursor,
        'latest_task_turn': latest, 'run_deadline_epoch': time.time() + 60,
        'task_budget_turns_used': task_budget_turns_used, 'task_max_turns': 180,
        'stop_event': stopped, 'independent_probe_total_requests': 0,
        'completion_receipts': receipts, 'wake_receipts': None,
        'root_checkpoint_required': False, 'run_id': 'offline-run',
    }
    worker = threading.Thread(target=_worker, args=(config, commands, outputs), daemon=True)
    worker.start()
    try:
        assert outputs.get(timeout=10)['kind'] == 'ready'
        active.value = 1
        commands.put({'kind': 'completion', 'cursor': 1, 'request_id': 'completion-1',
                      'generation': 1, 'task_turn': 1})
        outcome = outputs.get(timeout=10)
        assert outcome['kind'] == 'completion' and outcome['decision'] == 'allow'
        assert outcome['request_id'] == 'completion-1'
        assert len(requests) == 2
        assert 'Task turns used: 179; limit: 180; remaining: 1.' in json.dumps(requests[0])
        assert 'Task turns used: 179; limit: 180; remaining: 1.' in json.dumps(requests[1])
        assert ROOT_SYSTEM_PROMPT in requests[1]['system']
        assert requests[1]['root_handoff'] == handoff
        receipts.put({'request_id': 'completion-1', 'accepted': False})
    finally:
        stopped.set()
        commands.put({'kind': 'close'})
        worker.join(timeout=10)
    assert not worker.is_alive()
