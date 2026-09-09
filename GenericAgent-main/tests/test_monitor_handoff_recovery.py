import json
import queue
import threading

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.runtime import MonitorRuntime, _worker
from ga_monitor_adapter import GenericAgentMonitorAdapter


class ThreadProcess:
    def __init__(self, target, args, daemon):
        self.thread = threading.Thread(target=target, args=args, daemon=daemon)

    def start(self):
        self.thread.start()

    def is_alive(self):
        return self.thread.is_alive()

    def join(self, timeout):
        self.thread.join(timeout)

    def terminate(self):
        raise AssertionError('Fixture must exit on close')


def late_worker(config, commands, outputs):
    first = commands.get()
    outputs.put(dict(kind='intervention', message='Correct the actual discrepancy',
                     request_id='first-correction'))
    second = commands.get()
    # The expired approval must never approve the second request.
    outputs.put(dict(kind='completion', decision='allow', cursor=first['cursor'],
                     request_id=first['request_id']))
    outputs.put(dict(kind='completion', decision='continue', message='Current correction',
                     cursor=second['cursor'], request_id=second['request_id']))
    while commands.get()['kind'] != 'close':
        pass


def test_late_approval_is_archived_not_delivered_to_next_request(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    runtime = MonitorRuntime(
        public_task='Original requirements', task_workspace=workspace,
        artifact_dir=tmp_path / 'audit', config_name='fixture', model_config={},
        interrupt_callback=lambda _: None, worker_target=late_worker,
        process_factory=ThreadProcess, completion_timeout=1,
    )
    try:
        first = runtime.request_completion({'internal_turn': 57})
        assert first.reason == 'interrupted'
        second = runtime.request_completion({'internal_turn': 59})
        assert not second.allow
        assert second.message == 'Current correction'
        assert not runtime._pending
        assert runtime.task_original_path.parent == workspace
        assert runtime.task_original_path.read_text(encoding='utf-8') == 'Original requirements'
    finally:
        runtime.close()
    receipts = [json.loads(x) for x in
                (tmp_path / 'audit/runtime_receipts.jsonl').read_text().splitlines()]
    assert any(r.get('delivery') == 'archived_late_or_unmatched' for r in receipts)


def test_worker_handoff_does_not_prejudge_question_and_echoes_request(monkeypatch, tmp_path):
    from monitor_agent_core import agent, provider
    contexts = []

    class Client:
        def __init__(self, *args):
            pass

    class Monitor:
        def __init__(self, *args):
            pass

        def review(self, context, completion_pending=False):
            contexts.append(context)
            if completion_pending:
                return MonitorAction('intervene', {'message': 'Here are the missing requirements.'})
            return MonitorAction('wait', {'after_turns': 1})

    monkeypatch.setattr(provider, 'MonitorProviderClient', Client)
    monkeypatch.setattr(agent, 'MonitorAgent', Monitor)
    evidence, private, workspace = [tmp_path / n for n in ('evidence', 'private', 'workspace')]
    for path in (evidence, private, workspace):
        path.mkdir()
    commands, outputs = queue.Queue(), queue.Queue()
    thread = threading.Thread(target=_worker, args=({
        'config_name': 'fixture', 'model_config': {}, 'evidence_root': str(evidence),
        'private_root': str(private), 'task_workspace': str(workspace),
        'task_original_path': str(workspace / 'original.txt'), 'max_review_turns': 20,
    }, commands, outputs))
    thread.start()
    try:
        assert outputs.get(timeout=2)['kind'] == 'ready'
        (private / 'delivery_feedback.jsonl').write_text(
            json.dumps({'delivery': 'archived_late_or_unmatched', 'message': 'previous correction'}) + '\n', encoding='utf-8')
        commands.put({'kind': 'completion', 'cursor': 7, 'request_id': 'r7', 'task_turn': 4})
        result = outputs.get(timeout=2)
        assert result['request_id'] == 'r7'
        assert result['message'] == 'Here are the missing requirements.'
        assert 'may claim completion, ask for clarification' in contexts[1]
        assert str(workspace / 'original.txt') in contexts[0]
        assert 'Orient yourself, then choose wait' not in contexts[0]
        assert 'archived_late_or_unmatched' in contexts[1]
    finally:
        commands.put({'kind': 'close'})
        thread.join(2)
    assert not thread.is_alive()


def test_adapter_preserves_question_as_neutral_handoff():
    from monitor_agent_core.runtime import CompletionOutcome
    captured = []

    class Runtime:
        def request_completion(self, event):
            captured.append(event)
            return CompletionOutcome(False, 'Original requirements are ...', 'monitor_correction')

    adapter = object.__new__(GenericAgentMonitorAdapter)
    adapter.runtime = Runtime()
    result = adapter.review_completion(None, 293, response_content='What were the seven targets?')
    assert captured[0]['boundary'] == 'task_control_handoff'
    assert captured[0]['response_content'] == 'What were the seven targets?'
    assert result.next_prompt == 'Original requirements are ...'


def test_clean_monitor_blocked_review_does_not_block_publication(tmp_path):
    entered, release = threading.Event(), threading.Event()

    def blocked_worker(config, commands, outputs):
        entered.set()
        release.wait()
        while commands.get()['kind'] != 'close':
            pass

    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    runtime = MonitorRuntime(
        public_task='task', task_workspace=workspace, artifact_dir=tmp_path / 'audit',
        config_name='fixture', model_config={}, interrupt_callback=lambda _: None,
        worker_target=blocked_worker, process_factory=ThreadProcess,
    )
    published = threading.Event()

    def publish():
        for turn in range(10):
            runtime.archive_boundary({'internal_turn': turn, 'response_content': 'Working'})
        published.set()

    publisher = threading.Thread(target=publish)
    try:
        assert entered.wait(2)
        publisher.start()
        assert published.wait(2), 'Publication must not wait for monitor review'
        assert not release.is_set()
    finally:
        release.set()
        publisher.join(2)
        runtime.close()
