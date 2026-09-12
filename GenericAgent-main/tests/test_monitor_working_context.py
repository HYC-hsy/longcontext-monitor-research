import json

import pytest

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
from monitor_agent_core.working_context import current_working_context


@pytest.fixture
def workspace(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    return MonitorWorkspace(evidence, tmp_path / 'private')


def client():
    obj = MonitorProviderClient.__new__(MonitorProviderClient)
    obj.config = {'monitor_active_working_context': True}
    obj.history = [{'role': 'user', 'content': [{'type': 'text', 'text': 'existing dialogue'}]}]
    return obj


def test_missing_empty_and_bounded_note(workspace):
    assert current_working_context(workspace) is None
    workspace.write_text('monitor/working.md', '  ')
    assert current_working_context(workspace) is None
    workspace.write_text('monitor/working.md', 'abcdefghijk')
    result = current_working_context(workspace, limit=5)
    assert 'Only the first 5' in result
    assert 'abcde' in result and 'fghijk' not in result
    assert workspace.read_text('monitor/working.md')['content'] == 'abcdefghijk'


def test_same_request_uses_latest_note_without_history_growth(workspace):
    obj = client()
    MonitorAgent(obj, workspace)
    original = list(obj.history)
    seen = []
    obj._request_with_recovery = lambda tools: seen.append(obj.history[-1]['content'][0]['text'])
    workspace.write_text('monitor/working.md', 'First hypothesis')
    obj._request([{'tool': 'fixture'}])
    workspace.patch_text('monitor/working.md', 'First hypothesis', 'Revised understanding')
    obj._request([{'tool': 'fixture'}])
    assert 'First hypothesis' in seen[0]
    assert 'Revised understanding' in seen[1] and 'First hypothesis' not in seen[1]
    assert obj.history == original
    records = [json.loads(line) for line in (workspace.private_root / 'audit/dialogue.jsonl').read_text().splitlines()]
    assert len(records) == 2 and records[-1]['content'] == seen[-1]


def test_failure_restores_history_and_maintenance_does_not_inject(workspace):
    obj = client()
    MonitorAgent(obj, workspace)
    workspace.write_text('monitor/working.md', 'Private understanding')
    original = list(obj.history)
    def fail(tools):
        assert len(obj.history) == len(original) + 1
        raise RuntimeError('fixture failure')
    obj._request_with_recovery = fail
    with pytest.raises(RuntimeError):
        obj._request([{}])
    assert obj.history == original
    obj._request_with_recovery = lambda tools: list(obj.history)
    assert obj._request([]) == original


def test_disabled_candidate_does_not_add_callback(workspace):
    obj = client()
    obj.config = {}
    MonitorAgent(obj, workspace)
    assert not hasattr(obj, 'prepare_active_context')


def test_no_cross_task_note_and_deleted_note_not_reused(workspace, tmp_path):
    workspace.write_text('monitor/working.md', 'Task one')
    other = MonitorWorkspace(workspace.evidence_root, tmp_path / 'second-private')
    assert current_working_context(other) is None
    workspace.resolve_private('monitor/working.md').unlink()
    assert current_working_context(workspace) is None


def test_invalid_flag_rejected(workspace):
    obj = client()
    obj.config['monitor_active_working_context'] = 'false'
    with pytest.raises(ValueError, match='must be a boolean'):
        MonitorAgent(obj, workspace)


def test_complete_reads_after_compaction_and_preserves_tool_receipt(workspace):
    obj = client()
    MonitorAgent(obj, workspace)
    obj.usage_records = []
    obj._compact_history = lambda: workspace.write_text('monitor/working.md', 'New handoff')
    def request(tools):
        assert 'New handoff' in obj.history[-1]['content'][0]['text']
        assert obj.history[-2]['content'][0]['type'] == 'tool_result'
        return [{'type': 'text', 'text': 'continue'}], {}
    obj._request_with_recovery = request
    obj.complete([{'role': 'user', 'tool_results': [
        {'tool_use_id': 'c1', 'content': 'public result'}]}], [{}])
    assert obj.history[-1]['role'] == 'assistant'
    assert obj.history[-2]['content'][0]['tool_use_id'] == 'c1'
    assert 'New handoff' not in json.dumps(obj.history)
