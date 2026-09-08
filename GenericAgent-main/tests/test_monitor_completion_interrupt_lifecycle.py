"""Completion waits must yield to corrections without duplicate model work."""

import json
import queue
import threading
import time

from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.runtime import MonitorRuntime, _coalesce_wake_command
from task_interruption import ResumableInterruption


def await_condition(predicate):
    deadline = time.monotonic() + 3
    while not predicate():
        assert time.monotonic() < deadline
        time.sleep(.01)


def test_actual_worker_correction_resumes_wait_and_skips_stale_review(tmp_path, monkeypatch):
    entered, send, sent, finish = (threading.Event() for _ in range(4))
    stale_skipped = threading.Event()
    calls = []
    mailbox = ResumableInterruption()

    class Provider:
        def __init__(self, *args): pass

    class Monitor:
        def __init__(self, *args): pass

        def review(self, context, completion_pending=False):
            calls.append(completion_pending)
            if len(calls) == 1:
                entered.set()
                assert send.wait(3)
                self.intervention_callback('Inspect the actual test assertion.')
                sent.set()
                assert finish.wait(3)
                return MonitorAction('wait', {'after_turns': 1000})
            assert completion_pending
            return MonitorAction('allow_complete', {})

    monkeypatch.setattr('monitor_agent_core.provider.MonitorProviderClient', Provider)
    monkeypatch.setattr('monitor_agent_core.agent.MonitorAgent', Monitor)
    def observe_coalescing(commands, first, completion_is_active=None):
        def checked(command):
            active = completion_is_active(command)
            if not active:
                stale_skipped.set()
            return active
        return _coalesce_wake_command(commands, first, checked)
    monkeypatch.setattr('monitor_agent_core.runtime._coalesce_wake_command', observe_coalescing)
    (tmp_path / 'workspace').mkdir()
    runtime = MonitorRuntime(
        public_task='Implement the behavior.', task_workspace=tmp_path / 'workspace',
        artifact_dir=tmp_path / 'monitor', config_name='fake', model_config={},
        interrupt_callback=mailbox.request, interrupt_pending=mailbox.is_requested,
        process_factory=threading.Thread, completion_timeout=3,
    )
    results = []
    waiter = None
    try:
        assert entered.wait(2)
        # Publication remains nonblocking while the monitor is blocked.
        started = time.monotonic()
        runtime.archive_boundary({'internal_turn': 1, 'response_content': 'Working'})
        assert time.monotonic() - started < .2
        waiter = threading.Thread(target=lambda: results.append(runtime.request_completion(
            {'internal_turn': 2, 'response_content': 'Complete'})))
        waiter.start()
        await_condition(lambda: bool(runtime._pending))
        send.set()
        assert sent.wait(2)
        waiter.join(2)
        assert not waiter.is_alive()  # The current monitor review has NOT ended.
        assert not finish.is_set()
        assert results[0].reason == 'interrupted'
        assert not results[0].allow
        assert mailbox.consume()[0]['message'] == 'Inspect the actual test assertion.'
        assert mailbox.consume() == []
        assert runtime._active_completion.value == 0
        finish.set()
        assert stale_skipped.wait(2)
        assert calls == [False]
        # Only a fresh completion may cause another completion review.
        fresh = runtime.request_completion({'internal_turn': 3, 'response_content': 'Repaired'})
        assert fresh.allow
        assert calls == [False, True]
        await_condition(lambda: (runtime.private_root / 'delivery_feedback.jsonl').exists())
        receipts = [json.loads(x) for x in
                    (runtime.private_root / 'delivery_feedback.jsonl').read_text().splitlines()]
        corrections = [x for x in receipts if x['kind'] == 'intervention']
        assert len(corrections) == 1
        assert len(corrections[0]['resumed_completion_requests']) == 1
    finally:
        send.set()
        finish.set()
        if waiter is not None: waiter.join(3)
        runtime.close()


class IdleProcess:
    def __init__(self, **kwargs): pass
    def start(self): pass
    def is_alive(self): return True
    def join(self, timeout=None): pass
    def terminate(self): pass


def idle_runtime(tmp_path, callback, pending=lambda: False):
    (tmp_path / 'workspace').mkdir()
    return MonitorRuntime(
        public_task='task', task_workspace=tmp_path / 'workspace',
        artifact_dir=tmp_path / 'monitor', config_name='fake', model_config={},
        interrupt_callback=callback, interrupt_pending=pending,
        process_factory=IdleProcess, completion_timeout=1,
    )


def test_already_delivered_correction_does_not_start_completion_wait(tmp_path):
    mailbox = ResumableInterruption()
    mailbox.request('A correction arrived immediately before the handoff.')
    runtime = idle_runtime(tmp_path, mailbox.request, mailbox.is_requested)
    try:
        result = runtime.request_completion({'internal_turn': 2})
        assert result.reason == 'interrupted'
        assert not runtime._pending
        assert runtime._active_completion.value == 0
        assert len(mailbox.consume()) == 1
    finally:
        runtime.close()


def test_failed_delivery_does_not_release_completion(tmp_path):
    def fail(message): raise OSError('interrupt delivery failed')
    runtime = idle_runtime(tmp_path, fail)
    results = []
    waiter = threading.Thread(target=lambda: results.append(runtime.request_completion()))
    try:
        waiter.start()
        command = runtime._commands.get(timeout=2)
        runtime._outputs.put({'kind': 'intervention', 'message': 'check', 'request_id': 'i'})
        feedback = runtime.private_root / 'delivery_feedback.jsonl'
        await_condition(feedback.exists)
        assert json.loads(feedback.read_text().splitlines()[0])['delivery'] == 'failed'
        assert waiter.is_alive()
        runtime._outputs.put({'kind': 'completion', 'decision': 'continue',
                              'request_id': command['request_id'], 'message': 'Fix the test.'})
        waiter.join(2)
        assert results[0].message == 'Fix the test.'
        assert results[0].reason == 'monitor_correction'
    finally:
        waiter.join(2)
        runtime.close()


def test_expired_completion_reply_cannot_approve_next_proposal(tmp_path):
    runtime = idle_runtime(tmp_path, lambda _: None)
    results = []
    first = threading.Thread(target=lambda: results.append(runtime.request_completion()))
    second = None
    try:
        first.start()
        old = runtime._commands.get(timeout=2)
        first.join(2)
        assert results[0].reason == 'timeout'
        assert runtime._active_completion.value == 0
        second = threading.Thread(target=lambda: results.append(runtime.request_completion()))
        second.start()
        new = runtime._commands.get(timeout=2)
        runtime._outputs.put({'kind': 'completion', 'decision': 'allow', 'request_id': old['request_id']})
        feedback = runtime.private_root / 'delivery_feedback.jsonl'
        await_condition(feedback.exists)
        assert json.loads(feedback.read_text().splitlines()[0])['delivery'] == 'archived_late_or_unmatched'
        assert second.is_alive()
        assert runtime._active_completion.value == new['generation']
        runtime._outputs.put({'kind': 'completion', 'decision': 'allow', 'request_id': new['request_id']})
        second.join(2)
        assert results[1].allow
    finally:
        first.join(2)
        if second is not None: second.join(2)
        runtime.close()


def test_expired_completion_does_not_swallow_new_patrol_progress():
    commands = queue.Queue()
    commands.put({'kind': 'boundary', 'cursor': 250})
    expired = {'kind': 'completion', 'generation': 1, 'cursor': 227}
    selected = _coalesce_wake_command(commands, expired, lambda c: False)
    assert selected == {'kind': 'boundary', 'cursor': 250}
    assert _coalesce_wake_command(commands, expired, lambda c: False) is None
