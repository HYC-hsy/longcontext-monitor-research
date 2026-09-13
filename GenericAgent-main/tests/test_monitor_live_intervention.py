import json
import queue
import threading

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import ModelResponse, ToolCall
from monitor_agent_core.workspace import MonitorWorkspace


class Client:
    config = {}
    def __init__(self, actions, sent):
        self.actions = iter(actions)
        self.sent = sent
        self.steps = 0
    def history_measure(self): return {}
    def export_history(self): return []
    def complete(self, messages, tools):
        action = next(self.actions)
        if self.steps > 0:
            assert self.sent == ['Check the conflicting test expectation.']
        self.steps += 1
        name, args = action
        return ModelResponse('', [ToolCall(str(self.steps), name, json.dumps(args))], {})


def test_completion_arrives_inside_same_review(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'fact.txt').write_text('public fact')
    state = [None]

    class ArrivingClient(Client):
        def complete(self, messages, tools):
            self.steps += 1
            if self.steps == 1:
                state[0] = {'generation': 1, 'request_id': 'completion-1', 'cursor': 9}
                return ModelResponse('', [ToolCall('1', 'file_read', '{"path":"task/fact.txt"}')], {})
            assert any('line 9' in str(m.get('content')) for m in messages)
            return ModelResponse('', [ToolCall('2', 'allow_complete', '{}')], {})

    client = ArrivingClient([], [])
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))
    monitor.completion_state = lambda: state[0]
    result = monitor.review('Ordinary progress', completion_pending=False)
    assert result.payload == {'request_id': 'completion-1'}
    assert client.steps == 2


def test_approval_cannot_rebind_to_unseen_proposal(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    monitor = MonitorAgent(Client([], []), MonitorWorkspace(evidence, tmp_path / 'private'))
    state = [{'generation': 1, 'request_id': 'completion-1', 'cursor': 9}]
    monitor.completion_state = lambda: state[0]
    monitor._refresh_completion()
    state[0] = {'generation': 2, 'request_id': 'completion-2', 'cursor': 19}
    assert monitor.dispatch('allow_complete', {}).data['status'] == 'error'
    monitor._refresh_completion()
    assert monitor.dispatch('allow_complete', {}).action.payload['request_id'] == 'completion-2'
    monitor.intervention_callback = lambda message: {'delivery': 'queued'}
    monitor.dispatch('intervene', {'message': 'A concrete conflict'})
    # The parent pump may not yet have invalidated shared state.
    monitor._refresh_completion()
    assert monitor.dispatch('allow_complete', {}).action is None


def test_pending_wait_keeps_investigation_open_without_task_input(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    monitor = MonitorAgent(Client([], []), MonitorWorkspace(evidence, tmp_path / 'private'))
    state = [{'generation': 1, 'request_id': 'completion-1', 'cursor': 9}]
    monitor.completion_state = lambda: state[0]
    # A proposal arriving after the model request also prevents a turn-based deadlock.
    result = monitor.dispatch('wait', {'after_turns': 1})
    assert result.action is None
    assert result.data['status'] == 'handoff_pending'
    state[0] = None
    assert monitor.dispatch('wait', {'after_turns': 1}).action.kind == 'wait'


def test_intervention_delivers_before_followup_tools_and_wait(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'response.txt').write_text('I will compare the original requirement.')
    sent = []
    c = Client([
        ('intervene', {'message': 'Check the conflicting test expectation.'}),
        ('file_read', {'path': 'task/response.txt'}),
        ('wait', {'after_turns': 1}),
    ], sent)
    m = MonitorAgent(c, MonitorWorkspace(evidence, tmp_path / 'private'))
    m.intervention_callback = lambda message: sent.append(message) or {'delivery': 'queued'}
    result = m.review('Inspect progress', completion_pending=True)
    assert result.kind == 'wait'
    assert c.steps == 3
    assert not m.completion_pending


def test_no_duplicate_or_stale_completion_after_submission(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    sent = []
    m = MonitorAgent(Client([], sent), MonitorWorkspace(evidence, tmp_path / 'private'))
    m.intervention_callback = lambda message: sent.append(message)
    m.completion_pending = True
    args = {'message': 'Check the conflicting test expectation.'}
    assert m.dispatch('intervene', args).action is None
    assert m.dispatch('intervene', args).data['status'] == 'already_submitted'
    assert len(sent) == 1
    assert m.dispatch('allow_complete', {}).action is None
    assert 'No root completion' in m.dispatch('allow_complete', {}).data['error']


def test_failed_submission_is_not_marked_delivered(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    m = MonitorAgent(Client([], []), MonitorWorkspace(evidence, tmp_path / 'private'))
    def fail(message): raise OSError('queue unavailable')
    m.intervention_callback = fail
    m.completion_pending = True
    result = m.dispatch('intervene', {'message': 'Check evidence'})
    assert result.data['status'] == 'error'
    assert not m._sent_messages
    assert m.completion_pending


@pytest.mark.parametrize('at_completion', [False, True])
def test_worker_submits_while_same_review_is_still_running(tmp_path, monkeypatch, at_completion):
    from monitor_agent_core.runtime import _worker
    from monitor_agent_core.actions import MonitorAction
    entered = threading.Event()
    release = threading.Event()
    commands, outputs = queue.Queue(), queue.Queue()

    class Provider:
        def __init__(self, *args): pass

    class Monitor:
        def __init__(self, *args, **kwargs): self.calls = 0
        def review(self, context, completion_pending=False):
            self.calls += 1
            if at_completion and self.calls == 1:
                return MonitorAction('wait', {'after_turns': 1})
            self.intervention_callback('Inspect the conflicting evidence')
            entered.set()
            assert release.wait(3)
            return MonitorAction('wait', {'after_turns': 2})

    monkeypatch.setattr('monitor_agent_core.provider.MonitorProviderClient', Provider)
    monkeypatch.setattr('monitor_agent_core.agent.MonitorAgent', Monitor)
    for name in ['evidence', 'private', 'workspace']:
        (tmp_path / name).mkdir()
    config = dict(config_name='fake', model_config={}, max_review_turns=20,
                  evidence_root=str(tmp_path / 'evidence'), private_root=str(tmp_path / 'private'),
                      task_workspace=str(tmp_path / 'workspace'), task_original_path='/app/input.txt',
                      stop_event=threading.Event())
    if at_completion:
        commands.put({'kind': 'completion', 'cursor': 5, 'task_turn': 3, 'request_id': 'pending-1'})
    worker = threading.Thread(target=_worker, args=(config, commands, outputs))
    worker.start()
    try:
        if at_completion:
            assert outputs.get(timeout=2)['kind'] == 'ready'
        assert entered.wait(2)
        result = outputs.get(timeout=2)
        assert result['kind'] == ('completion' if at_completion else 'intervention')
        if at_completion:
            assert result['request_id'] == 'pending-1'
            assert result['decision'] == 'continue'
        assert worker.is_alive()  # delivery occurred before the model chose wait
    finally:
        commands.put({'kind': 'close'})
        release.set()
        worker.join(3)
    assert not worker.is_alive()
    remaining = []
    while not outputs.empty(): remaining.append(outputs.get_nowait())
    assert not any(x['kind'] in ['intervention', 'completion'] for x in remaining)
