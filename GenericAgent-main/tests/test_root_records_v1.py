"""Zero-model contract for the opt-in root-entry history projection."""

import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.root_records_v1 import canonical, parse_ledger, project
from test_crs_v0 import fixture


def _history():
    return [
        {'role': 'user', 'content': [{'type': 'text', 'text': 'Original task evidence'}]},
        {'role': 'assistant', 'content': [
            {'type': 'thinking', 'thinking': 'Old progress claim', 'signature': 'sig'},
            {'type': 'tool_use', 'id': 'old-1', 'name': 'file_read', 'input': {'path': 'a.py'}}]},
        {'role': 'user', 'content': [
            {'type': 'tool_result', 'tool_use_id': 'old-1', 'content': 'historical result'}]},
        {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Verified earlier'}]},
    ]


def test_different_history_lengths_round_trip_and_noop():
    for history in (_history(), _history() + _history()[:1]):
        projected, manifest, source = project(history)
        assert manifest['applied'] is True
        assert source == canonical(history)
        decoded = parse_ledger(projected[0]['content'][0]['text'])
        assert len(decoded) == 3 if len(history) == 4 else len(decoded) == 4
        assert 'Verified earlier' not in projected[0]['content'][0]['text']
        assert 'historical result' in projected[0]['content'][0]['text']
    no_op = [{'role': 'user', 'content': [{'type': 'text', 'text': 'No old assistant text'}]}]
    assert project(no_op)[0] == no_op
    assert project(no_op)[1]['applied'] is False


def test_unknown_schema_or_open_exchange_fails_before_projection():
    history = _history()
    history[2]['content'][0]['is_error'] = True
    with pytest.raises(ValueError, match='Unknown'):
        project(history)
    open_history = _history()[:2]
    with pytest.raises(ValueError, match='Unclosed'):
        project(open_history)


def test_live_root_hook_once_per_handoff_and_archive(tmp_path):
    monitor, client, workspace, handoff = fixture(tmp_path, rhr=True, rer=True)
    monitor.history_projection = 'root_records_v1'
    monitor.frame_kind = 'local'
    client.restore_history(_history())
    monitor._enter_root_frame(handoff)
    first = client.export_history()
    assert len(first) == 1 and 'Verified earlier' not in json.dumps(first)
    assert monitor._local_history_at_root == first
    archives = list((workspace.private_root / 'audit/root_projections').rglob('source.json'))
    assert len(archives) == 1
    assert json.loads(archives[0].read_text(encoding='utf-8')) == _history()
    monitor._enter_root_frame(handoff)
    assert client.export_history() == first
    assert len(list((workspace.private_root / 'audit/root_projections').rglob('source.json'))) == 1
    next_handoff = {'request_id': 'completion-2', 'generation': 2, 'cursor': 2}
    monitor.completion_state = lambda: next_handoff
    monitor._enter_root_frame(next_handoff)
    assert len(list((workspace.private_root / 'audit/root_projections').rglob('source.json'))) == 2


def test_projection_config_is_default_off_and_requires_bji(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path, rhr=True, rer=True)
    assert monitor.history_projection == 'off'
    config = dict(client.config, monitor_history_projection='root_records_v1')
    assert MonitorAgent(MonitorProviderClient('anthropic', config), workspace).history_projection == 'root_records_v1'
    config['monitor_root_epistemic_reestimation'] = False
    with pytest.raises(ValueError, match='requires ASE'):
        MonitorAgent(MonitorProviderClient('anthropic', config), workspace)
