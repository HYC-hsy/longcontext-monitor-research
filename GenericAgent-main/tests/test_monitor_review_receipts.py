"""Real-provider history invariants for the Fyne R2 turn-20 failure shape."""
import json
from collections import Counter

import pytest

from monitor_agent_core.actions import MonitorAction, ToolOutcome
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.loop import MonitorLoopError, run_review
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


LAST_CALL = 'call_szlc7u2WcCssMd0c8x2SvSUl'


def call(cid, name='file_read', args=None):
    return {'type': 'tool_use', 'id': cid, 'name': name, 'input': args or {}}


def client_for(monkeypatch, batches):
    client = MonitorProviderClient('openai', {
        'apikey': 'test', 'apibase': 'https://example.test', 'model': 'gpt-test',
        'max_retries': 0})
    batches = iter(batches)
    monkeypatch.setattr(client, '_request_once', lambda tools: (next(batches), {}))
    return client


def receipts(client):
    return [b for m in client.history for b in m.get('content', [])
            if isinstance(b, dict) and b.get('type') == 'tool_result']


def assert_paired(client):
    wire = client._responses_history()
    calls = Counter(x['call_id'] for x in wire if x.get('type') == 'function_call')
    results = Counter(x['call_id'] for x in wire if x.get('type') == 'function_call_output')
    assert calls == results
    assert all(count == 1 for count in results.values())


def test_twentieth_tool_result_is_saved_before_budget_exit_and_next_wake(monkeypatch, tmp_path):
    batches = [[call(f'call-{i}')] for i in range(19)] + [[call(LAST_CALL)], [call('wait', 'wait')]]
    client = client_for(monkeypatch, batches)
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))
    invoked = []

    def dispatch(name, args):
        if name == 'wait':
            return ToolOutcome({}, action=MonitorAction('wait', {'after_turns': 2}))
        invoked.append(name)
        return ToolOutcome({'content': 'public evidence', 'sequence': len(invoked)})

    monkeypatch.setattr(monitor, 'dispatch', dispatch)
    with pytest.raises(MonitorLoopError, match='20 turns'):
        monitor.review('Inspect public task progress.')
    assert len(invoked) == 20
    assert_paired(client)
    last = receipts(client)[-1]
    assert last['tool_use_id'] == LAST_CALL
    assert json.loads(last['content'])['sequence'] == 20
    saved = json.loads((tmp_path / 'private/audit/provider_history.json').read_text())
    assert saved == client.export_history()
    assert monitor.review('Continue from the previous evidence.').kind == 'wait'
    assert_paired(client)
    assert len(invoked) == 20  # No tool replay or extra API turn to close history.


def test_normal_continuation_and_terminal_batch_do_not_duplicate(monkeypatch):
    client = client_for(monkeypatch, [[call('read')],
        [call('read2'), call('wait', 'wait'), call('skipped')]])
    invoked = []

    def dispatch(name, args):
        invoked.append(name)
        return ToolOutcome({'value': 3}, action=MonitorAction('wait', {}) if name == 'wait' else None)

    assert run_review(client, 'system', 'wake', [], dispatch).kind == 'wait'
    assert_paired(client)
    assert invoked == ['file_read', 'file_read', 'wait']
    assert json.loads(receipts(client)[-1]['content'])['status'] == 'not_executed'


def test_dispatch_failure_preserves_completed_unknown_and_unexecuted(monkeypatch):
    client = client_for(monkeypatch, [[call('done'), call('failed', 'code_run'), call('not-run')]])
    invoked = []

    def dispatch(name, args):
        invoked.append(name)
        if name == 'code_run':
            raise TimeoutError('execution outcome cannot be inferred')
        return ToolOutcome({'actual': 'result'})

    with pytest.raises(TimeoutError):
        run_review(client, 'system', 'wake', [], dispatch)
    assert_paired(client)
    data = [json.loads(x['content']) for x in receipts(client)]
    assert data[0] == {'actual': 'result'}
    assert data[1]['status'] == 'execution_unconfirmed'
    assert data[1]['error_type'] == 'TimeoutError'
    assert data[2]['status'] == 'not_executed'
    assert invoked == ['file_read', 'code_run']


def test_before_model_failure_preserves_pending_results(monkeypatch):
    client = client_for(monkeypatch, [[call('done')]])
    count = 0

    def before_model():
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('maintenance failed')

    with pytest.raises(RuntimeError, match='maintenance failed'):
        run_review(client, 'system', 'wake', [], lambda *a: ToolOutcome({'actual': 1}),
                   before_model=before_model)
    assert_paired(client)


def test_last_batch_preserves_multiple_results(monkeypatch):
    client = client_for(monkeypatch, [[call('first'), call('last')]])
    with pytest.raises(MonitorLoopError):
        run_review(client, 'system', 'wake', [], lambda *a: ToolOutcome({'value': 7}), max_turns=1)
    assert_paired(client)
    assert len(receipts(client)) == 2


def test_request_failure_does_not_double_commit_previous_receipts(monkeypatch):
    client = client_for(monkeypatch, [[call('done')]])
    request = client._request_once
    calls = 0

    def fail_second(tools):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError('request failed after history append')
        return request(tools)

    monkeypatch.setattr(client, '_request_once', fail_second)
    with pytest.raises(RuntimeError):
        run_review(client, 'system', 'wake', [], lambda *a: ToolOutcome({'value': 7}))
    assert_paired(client)
    assert len(receipts(client)) == 1
