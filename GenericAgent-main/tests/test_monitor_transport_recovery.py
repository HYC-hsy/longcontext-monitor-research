"""No network: reproduce transport failure while a root handoff is pending."""
import json
import threading
import time

import pytest
import requests

from monitor_agent_core.provider import (
    MonitorProviderClient, ProviderError, ProviderRecoveryExhausted,
    RetryableProviderError, _remote_error,
)
from monitor_agent_core.actions import MonitorAction
from monitor_agent_core.runtime import MonitorRuntime
from test_monitor_handoff_recovery import ThreadProcess


class FastStop:
    def __init__(self, cancel=False):
        self.delays = []
        self.cancel = cancel

    def is_set(self):
        return False

    def wait(self, seconds):
        self.delays.append(seconds)
        return self.cancel


def test_observed_queue_full_uses_existing_bounded_recovery(monkeypatch):
    c = client()
    def request(tools):
        raise _remote_error({'code': 'gateway_queue_full',
                             'message': 'Too many pending requests, please retry later'})
    monkeypatch.setattr(c, '_request_once', request)
    with pytest.raises(ProviderRecoveryExhausted):
        c.complete([{'role': 'user', 'content': 'Continue inspection'}], [])
    assert len(c.request_attempts) == 2
    assert c.recovery_stop.delays == [30.0]
    assert not isinstance(_remote_error({'type': 'authentication_error',
                                        'code': 'gateway_queue_full'}), RetryableProviderError)


def client():
    c = MonitorProviderClient('openai', {
        'apikey': 'fixture', 'apibase': 'https://invalid.example',
        'model': 'fixture', 'max_retries': 0,
    })
    c.recovery_deadline = time.monotonic() + 1000
    c.recovery_stop = FastStop()
    return c


def test_recovery_retries_same_request_without_duplicate_history(monkeypatch):
    c = client()
    observed = []

    def request(tools):
        observed.append(c.export_history())
        if len(observed) == 1:
            raise requests.ConnectionError('remote closed')
        return [{'type': 'text', 'text': 'recovered'}], {}

    monkeypatch.setattr(c, '_request_once', request)
    result = c.complete([{'role': 'user', 'content': 'inspect'}], [])
    assert result.content == 'recovered'
    assert observed[0] == observed[1]
    assert len(c.history) == 2
    assert c.recovery_stop.delays == [30.0]


@pytest.mark.parametrize('error', [ProviderError('bad request'), ValueError('bad local state')])
def test_permanent_error_does_not_enter_recovery(monkeypatch, error):
    c = client()
    def fail(tools):
        raise error
    monkeypatch.setattr(c, '_request_once', fail)
    with pytest.raises(type(error)):
        c.complete([{'role': 'user', 'content': 'inspect'}], [])
    assert c.recovery_stop.delays == []
    assert len(c.request_attempts) == 1


def test_transient_recovery_is_bounded(monkeypatch):
    c = client()
    def fail(tools):
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(c, '_request_once', fail)
    with pytest.raises(ProviderRecoveryExhausted):
        c.complete([{'role': 'user', 'content': 'inspect'}], [])
    assert len(c.request_attempts) == 2
    assert len(c.history) == 1  # No invented assistant answer.


def test_default_short_retries_allow_only_one_additional_batch(monkeypatch):
    c = client()
    c.max_retries = 2
    monkeypatch.setattr(c._cancelled, 'wait', lambda seconds: False)
    def fail(tools):
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(c, '_request_once', fail)
    with pytest.raises(ProviderRecoveryExhausted):
        c.complete([{'role': 'user', 'content': 'inspect'}], [])
    assert len(c.request_attempts) == 6
    assert c.recovery_stop.delays == [30.0]


def test_real_loop_preserves_tool_result_once_during_recovery(monkeypatch):
    from monitor_agent_core.loop import run_review
    from monitor_agent_core.actions import ToolOutcome
    c = client()
    snapshots, calls = [], []
    def request(tools):
        snapshots.append(c.export_history())
        if len(snapshots) == 1:
            return [{'type': 'tool_use', 'id': 'r1', 'name': 'read', 'input': {}}], {}
        if len(snapshots) == 2:
            raise requests.ConnectionError('remote closed')
        return [{'type': 'tool_use', 'id': 'w1', 'name': 'wait',
                 'input': {'after_turns': 1}}], {}
    def dispatch(name, args):
        calls.append(name)
        return (ToolOutcome({'evidence': 'exact'}) if name == 'read' else
                ToolOutcome({}, action=MonitorAction('wait', args)))
    monkeypatch.setattr(c, '_request_once', request)
    action = run_review(c, 'monitor', 'inspect', [], dispatch)
    assert action.kind == 'wait'
    assert calls == ['read', 'wait']
    assert snapshots[1] == snapshots[2]
    results = [b for m in c.history for b in m.get('content', [])
               if b.get('type') == 'tool_result']
    assert [b['tool_use_id'] for b in results] == ['r1', 'w1']


@pytest.mark.parametrize('cancel', [False, True])
def test_deadline_or_stop_prevents_additional_network(monkeypatch, cancel):
    c = client()
    c.recovery_stop = FastStop(cancel=True)
    if not cancel:
        c.recovery_deadline = time.monotonic() - 1
    attempts = []
    def fail(tools):
        attempts.append(1)
        raise requests.ConnectionError('offline')
    monkeypatch.setattr(c, '_request_once', fail)
    with pytest.raises(ProviderRecoveryExhausted):
        c.complete([{'role': 'user', 'content': 'inspect'}], [])
    assert len(attempts) == (1 if cancel else 0)


@pytest.mark.parametrize('ending', ['allow', 'intervene', 'fail'])
def test_pending_completion_survives_recovery_without_tool_replay(tmp_path, monkeypatch, ending):
    from monitor_agent_core import agent, provider
    entered, release = threading.Event(), threading.Event()
    instances, reviews, dispatched = [], [], []

    class Stop(FastStop):
        def wait(self, seconds):
            entered.set()
            assert release.wait(3)
            return False

    class Client(MonitorProviderClient):
        def __init__(self, *args):
            super().__init__('openai', {'apikey': 'fixture', 'apibase': 'https://invalid.example',
                                      'model': 'fixture', 'max_retries': 0})
            self.attempts = 0
            instances.append(self)

        def _request_once(self, tools):
            self.attempts += 1
            if self.attempts == 1 or ending == 'fail':
                raise requests.ConnectionError('remote closed')
            return [{'type': 'text', 'text': 'recovered'}], {}

    class Monitor:
        def __init__(self, c, *args, **kwargs):
            self.client = c

        def review(self, context, completion_pending=False):
            reviews.append(context)
            if len(reviews) == 1:
                return MonitorAction('wait', {'after_turns': 1})
            self.client.recovery_stop = Stop()
            # An already-executed tool must not be replayed after transport failure.
            dispatched.append('read')
            self.client.complete([{'role': 'user', 'content': 'original evidence'}], [])
            if ending == 'intervene':
                self.intervention_callback('Correct the concrete conflict')
                return MonitorAction('wait', {'after_turns': 1})
            current = self.completion_state()
            return MonitorAction('allow_complete', {'request_id': current['request_id']})

    monkeypatch.setattr(provider, 'MonitorProviderClient', Client)
    monkeypatch.setattr(agent, 'MonitorAgent', Monitor)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    delivered = []
    runtime = MonitorRuntime(task_id='fixture',
        public_task='Keep required behavior', task_workspace=workspace,
        artifact_dir=tmp_path / 'audit', config_name='fixture', model_config={},
        interrupt_callback=delivered.append, process_factory=ThreadProcess,
    )
    result = []
    waiter = None
    try:
        # Ordinary review starts, then completion arrives during recovery (R3 ordering).
        runtime.archive_boundary({'task_turn': 1})
        assert entered.wait(3)
        waiter = threading.Thread(target=lambda: result.append(
            runtime.request_completion({'task_turn': 2})))
        waiter.start()
        limit = time.monotonic() + 2
        while not runtime._pending and time.monotonic() < limit:
            time.sleep(.01)
        assert runtime._pending and waiter.is_alive()
        started = time.monotonic()
        runtime.archive_boundary({'task_turn': 3})
        assert time.monotonic() - started < .2  # No synchronous review on task path.
        assert not (runtime.artifact_dir / 'completion_incomplete.json').exists()
        release.set()
        waiter.join(3)
        assert not waiter.is_alive()
        if ending == 'allow':
            assert result[0].allow
        elif ending == 'intervene':
            assert result[0].reason == 'interrupted'
            assert delivered == ['Correct the concrete conflict']
        else:
            assert result[0].incomplete and not result[0].allow
            runtime._process.join(2)
            assert not runtime._process.is_alive()
            assert len(reviews) == 2  # Queued completion must not restart failed recovery.
        assert dispatched[:1] == ['read']
        assert len(instances) == 1
        assert instances[0].attempts >= 2
    finally:
        release.set()
        runtime.close()
        if waiter is not None:
            waiter.join(2)
