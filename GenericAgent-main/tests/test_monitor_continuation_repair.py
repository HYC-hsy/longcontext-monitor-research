import json
import time

import pytest

from monitor_agent_core.handoff_validation import note_text, ContinuationContractError
from monitor_agent_core.provider import HistoryCapacityError, ProviderRecoveryExhausted
from test_monitor_continuation_mode import setup_monitor, review
from test_monitor_continuation_diagnostics import stream


@pytest.mark.parametrize('reason,code', [('max_tokens', 'truncated_note'),
    ('tool_use', 'unexpected_tool'), ('refusal', 'abnormal_stop')])
def test_text_does_not_override_stop_reason(reason, code):
    with pytest.raises(ContinuationContractError) as caught:
        note_text([{'type': 'text', 'text': 'Looks like a valid note'}], {'stop_reason': reason})
    assert caught.value.code == code


@pytest.mark.parametrize('first', ['tool', 'truncated'])
def test_one_repair_preserves_context_and_accounts_usage(tmp_path, monkeypatch, first):
    client, monitor = setup_monitor(tmp_path)
    client.history = sum((review(i) for i in range(6)), [])
    original = client.export_history()
    calls = []
    def request(tools):
        assert tools == []
        assert client.history[:-1] == original
        calls.append(client.request_purpose)
        if len(calls) == 1 and first == 'tool':
            client.last_response_metadata = {'stop_reason': 'tool_use'}
            return [{'type': 'tool_use', 'name': 'intervene', 'id': 'rejected',
                     'input': {'message': 'NEVER_SEND'}}], {'output_tokens': 4}
        return client._parse_anthropic(stream('max_tokens' if len(calls) == 1 else 'end_turn'))
    monkeypatch.setattr(client, '_request', request)
    client._compact_history()
    assert calls == ['continuation', 'format_repair']
    assert 'uncertain grounds' in json.dumps(client.history)
    assert 'NEVER_SEND' not in json.dumps(client.history)
    assert len(client.usage_records) == 2
    assert client.usage_records[-1]['purpose'] == 'continuation_format_repair'
    assert len(list((monitor.workspace.private_root / 'audit/continuation_responses').glob('*.json'))) == 2


@pytest.mark.parametrize('cause', ['deadline', 'cancel'])
def test_no_repair_after_stop(tmp_path, monkeypatch, cause):
    client, monitor = setup_monitor(tmp_path)
    original = client.export_history()
    calls = []
    def request(tools):
        calls.append(1)
        if cause == 'deadline':
            client.recovery_deadline = time.monotonic() - 1
        else:
            client._cancelled.set()
        return [{'type': 'tool_use', 'name': 'wait'}], {}
    monkeypatch.setattr(client, '_request', request)
    with pytest.raises(ProviderRecoveryExhausted):
        monitor._prepare_continuation()
    assert len(calls) == 1
    assert client.history == original
    assert client.request_purpose == 'review'


def test_abnormal_stop_not_blindly_retried(tmp_path, monkeypatch):
    client, monitor = setup_monitor(tmp_path)
    calls = []
    def request(tools):
        calls.append(1)
        return client._parse_anthropic(stream('refusal'))
    monkeypatch.setattr(client, '_request', request)
    with pytest.raises(ContinuationContractError, match='non-normal'):
        monitor._prepare_continuation()
    assert len(calls) == 1


def test_forced_compaction_then_replaced_root_uses_current_contract(tmp_path, monkeypatch):
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.pma_fused import ROOT_DECISION
    client, old_monitor = setup_monitor(tmp_path)
    client.config.update(monitor_pma_memory=True, monitor_root_decision_contract=True)
    monitor = MonitorAgent(client, old_monitor.workspace)
    (monitor.workspace.evidence_root / 'original_task.txt').write_text('Preserve behavior.', encoding='utf-8')
    client.history = sum((review(i) for i in range(6)), [])
    proposal = {'generation': 1, 'cursor': 1, 'request_id': 'root-1'}
    monitor.completion_state = lambda: dict(proposal)
    requests = []
    def request(tools):
        purpose = getattr(client, 'request_purpose', 'review')
        requests.append((purpose, client.system))
        if purpose == 'continuation':
            proposal.update(generation=2, cursor=2, request_id='root-2')
            return client._parse_anthropic(stream('end_turn'))
        if ROOT_DECISION not in client.system:
            return [{'type': 'text', 'text': '<maintenance_complete/>'}], {}
        assert monitor._seen_completion['generation'] == 2
        return [{'type': 'tool_use', 'name': 'allow_complete', 'id': 'allow', 'input': {}}], {}
    monkeypatch.setattr(client, '_request_once', request)
    result = monitor.review('root handoff', completion_pending=True)
    assert result.kind == 'allow_complete'
    assert result.payload['request_id'] == 'root-2'
    assert any(purpose == 'continuation' for purpose, _ in requests)
    assert ROOT_DECISION in requests[-1][1]
    assert sum(ROOT_DECISION in system for purpose, system in requests if purpose == 'review') == 1
