"""Zero-model CRS-v0 release and provenance checks."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent, crs_tools
from monitor_agent_core.crs_v0 import validate_contrast
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def fixture(tmp_path):
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    (evidence / 'original_task.txt').write_text('The route must remain public.', encoding='utf-8')
    event = {'archive_sequence': 1, 'task_turn': 8, 'boundary': 'post_tool_pre_next_llm',
             'text': 'The route check ran.', 'tool_calls': [{'name': 'code_run', 'id': 't1'}],
             'tool_results': [{'tool_use_id': 't1', 'content': '{"status":"success"}'}]}
    (evidence / 'public_events.jsonl').write_text(json.dumps(event) + '\n', encoding='utf-8')
    task = tmp_path / 'task'
    task.mkdir()
    (task / 'route.py').write_text('ROUTE = True\n', encoding='utf-8')
    workspace = MonitorWorkspace(evidence, tmp_path / 'private', {'workspace': task})
    client = MonitorProviderClient('anthropic', {
        'apikey': 'offline', 'apibase': 'https://offline.invalid', 'model': 'offline',
        'max_retries': 0, 'monitor_adaptive_supervisory_environment': True,
        'monitor_contrastive_release_state': True})
    monitor = MonitorAgent(client, workspace)
    workspace.write_text('monitor/reference.md', 'Durable public-route requirement.')
    handoff = {'request_id': 'completion-1', 'generation': 1, 'cursor': 1}
    monitor.completion_state = lambda: handoff
    monitor._seen_completion = handoff
    monitor.root_frame_handoff = handoff
    monitor.frame_kind = 'root'
    monitor.review_id = 'r1'
    monitor.dcm.begin_review('r1')
    monitor.situation.begin_review('r1')
    monitor.task_budget_state = lambda: (8, 300)
    return monitor, client, workspace, handoff


def contrast(**changes):
    value = {'alternative': 'The public route is absent.',
             'grounding': 'The public task requires the route.',
             'ground_refs': ['task/original_task.txt'],
             'discrimination': 'The observed route result would differ if it were absent.',
             'observation_refs': ['task/public_events.jsonl#1']}
    value.update(changes)
    return value


def events(workspace):
    path = workspace.private_root / 'audit/dialogue.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def expose(monitor, client):
    text = monitor._active_working_context()
    client._progress_request_id = 'request-next'
    monitor._cfs_context_appended()
    return text


def test_schema_tools_and_first_boundary(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    assert [x['function']['name'] for x in crs_tools()] == [x['function']['name'] for x in MONITOR_TOOLS]
    assert crs_tools()[-1]['function']['parameters']['required'] == ['contrast']
    assert monitor.dispatch('allow_complete', {}).action is None
    assert monitor.dispatch('allow_complete', {'contrast': contrast(ground_refs=[])}).action is None
    monitor.dcm.model_turn = 1
    first = monitor.dispatch('allow_complete', {'contrast': contrast()})
    assert first.action is None and first.data['status'] == 'release_not_executed'
    assert monitor.crs.root_contrast['surfaced'] is False
    shown = expose(monitor, client)
    assert 'Contrastive Release State' in shown and monitor.crs.root_contrast['canonical'] in shown
    assert monitor.crs.root_contrast['surfaced'] is True
    assert [r['event'] for r in events(workspace)].count('crs_surface_injected') == 1


def test_second_turn_exact_or_revised_contrast(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    assert monitor.dispatch('allow_complete', {'contrast': contrast()}).action is None
    # Two calls in the same provider response cannot use a pending surface.
    assert monitor.dispatch('allow_complete', {'contrast': contrast()}).action is None
    expose(monitor, client)
    monitor.dcm.model_turn = 2
    changed = contrast(alternative='A different public route is absent.')
    assert monitor.dispatch('allow_complete', {'contrast': changed}).action is None
    assert monitor.crs.root_contrast['surfaced'] is False
    assert monitor.dispatch('allow_complete', {'contrast': changed}).action is None
    expose(monitor, client)
    monitor.dcm.model_turn = 3
    assert monitor.dispatch('allow_complete', {'contrast': changed}).action.kind == 'allow_complete'
    assert monitor.crs.root_contrast is None
    names = [r['event'] for r in events(workspace)]
    assert names.count('crs_proposed') == 2 and 'crs_revised' in names and 'crs_confirmed' in names


def test_provider_ready_second_request_and_same_response_double_call(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path)
    snapshots = []

    def offline_response(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        calls = 2 if len(snapshots) == 1 else 1
        return ([{'type': 'tool_use', 'id': f'c{len(snapshots)}-{n}',
                  'name': 'allow_complete', 'input': {'contrast': contrast()}}
                 for n in range(calls)], {})

    monkeypatch.setattr(client, '_request_once', offline_response)
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete' and len(snapshots) == 2
    def visible(snapshot):
        return '\n'.join(block['text'] for message in snapshot['messages']
                         for block in message['content'] if block.get('type') == 'text')

    first = visible(snapshots[0])
    second = visible(snapshots[1])
    assert 'Contrastive Release State' not in first
    assert 'Contrastive Release State' in second
    assert json.dumps(contrast(), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')) in second
    assert len([r for r in events(workspace) if r['event'] == 'crs_release_attempted']) == 3
    assert len([r for r in events(workspace) if r['event'] == 'crs_confirmed']) == 1
    assert monitor.crs.root_contrast is None


def test_existing_and_new_observation_revision_without_required_new_measurement(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', {'contrast': contrast()})
    expose(monitor, client)
    monitor.dcm.model_turn = 2
    # An old completed observation is sufficient; no post-boundary tool is required.
    assert monitor.dispatch('allow_complete', {'contrast': contrast()}).action.kind == 'allow_complete'
    monitor.dcm.begin_review('r2')
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', {'contrast': contrast()})
    expose(monitor, client)
    monitor._audit_dialogue('tool_call', turn=2, tool_id='read-1', name='file_read',
                            arguments=json.dumps({'path': 'task/workspace/route.py'}))
    receipt = monitor.dispatch('file_read', {'path': 'task/workspace/route.py'}).data
    monitor._audit_dialogue('tool_result', turn=2, tool_id='read-1', data=receipt, action=None)
    locator = f'monitor/audit/dialogue.jsonl#{len(events(workspace))}'
    revised = contrast(observation_refs=[locator])
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', {'contrast': revised}).action is None
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['path'] == 'task/workspace/route.py'
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['start'] == receipt['start']
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['lines'] == receipt['lines']
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['sha256'] == receipt['sha256']


@pytest.mark.parametrize('lifecycle', [
    {'status': 'running', 'session_id': 's1', 'exit_code': None},
    {'status': 'cancelled', 'session_id': 's1', 'cancelled': True},
    {'status': 'error', 'error_type': 'TimeoutError', 'exit_code': 124},
    {'status': 'success', 'exit_code': 0},
])
def test_code_run_lifecycle_is_reported_without_semantic_verdict(tmp_path, lifecycle):
    _, _, workspace, _ = fixture(tmp_path)
    path = workspace.private_root / 'audit/dialogue.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{'event': 'tool_call', 'tool_id': 'c1', 'review_id': 'r1', 'name': 'code_run'},
             {'event': 'tool_result', 'tool_id': 'c1', 'review_id': 'r1', 'data': lifecycle}]
    path.write_text(''.join(json.dumps(row) + '\n' for row in lines), encoding='utf-8')
    _, _, proof = validate_contrast(contrast(observation_refs=['monitor/audit/dialogue.jsonl#2']), workspace)
    observed = proof['observation_refs'][0]
    assert observed['lifecycle'] == lifecycle
    assert not {'adequate', 'verified', 'supports_claim', 'alternative_excluded'} & set(observed)


@pytest.mark.parametrize('ref', ['monitor/audit/dialogue.jsonl#999',
                                 'monitor/audit/dialogue.jsonl#1',
                                 'task/public_events.jsonl#999', 'task/original_task.txt'])
def test_non_observation_or_missing_locator_rejected(tmp_path, ref):
    _, _, workspace, _ = fixture(tmp_path)
    (workspace.private_root / 'audit').mkdir()
    (workspace.private_root / 'audit/dialogue.jsonl').write_text(
        json.dumps({'event': 'tool_call', 'tool_id': 'x', 'name': 'file_read'}) + '\n', encoding='utf-8')
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_contrast(contrast(observation_refs=[ref]), workspace)


def test_grounding_existence_only_and_public_result_requirement(tmp_path):
    _, _, workspace, _ = fixture(tmp_path)
    value = contrast(grounding='Arbitrary model-authored grounding.', ground_refs=['monitor/reference.md'])
    assert validate_contrast(value, workspace)[2]['ground_refs'][0]['locator'] == 'monitor/reference.md'
    with pytest.raises((ValueError, FileNotFoundError)):
        validate_contrast(contrast(ground_refs=['task/public_events.jsonl#2']), workspace)
    event = {'archive_sequence': 2, 'task_turn': 9, 'boundary': 'post_model_pre_tool',
             'text': 'Claim only.', 'tool_calls': [], 'tool_results': []}
    with (workspace.evidence_root / 'public_events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(event) + '\n')
    with pytest.raises(ValueError, match='actual tool result'):
        validate_contrast(contrast(observation_refs=['task/public_events.jsonl#2']), workspace)


def test_intervention_stale_handoff_and_review_end_abandon(tmp_path):
    monitor, client, workspace, handoff = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', {'contrast': contrast()})
    expose(monitor, client)
    monitor.intervention_callback = lambda _: {'submission_id': 'queued', 'delivery': 'queued'}
    assert monitor.dispatch('intervene', {'message': 'Recheck the public route.'}).action.kind == 'root_intervened'
    assert monitor.crs.root_contrast is None
    monitor.dcm.begin_review('r2')
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', {'contrast': contrast()})
    handoff['generation'] = 2
    handoff['request_id'] = 'completion-2'
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', {'contrast': contrast()}).action is None
    assert monitor.crs.root_contrast['handoff']['generation'] == 2
    monitor.dcm.end_review('review_exhausted')
    assert monitor.crs.root_contrast is None
    assert not [r for r in events(workspace) if r['event'] == 'crs_confirmed']


def test_provider_failure_and_review_error_cannot_release(tmp_path):
    monitor, _, _, _ = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', {'contrast': contrast()})
    monitor.dcm.end_review('error')
    assert monitor.crs.root_contrast is None
    monitor.dcm.begin_review('r2')
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', {'contrast': contrast()}).action is None


def test_new_handoff_does_not_inherit_surfaced_contrast(tmp_path):
    monitor, client, _, handoff = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', {'contrast': contrast()})
    expose(monitor, client)
    handoff.update(request_id='completion-2', generation=2)
    monitor.dcm.model_turn = 2
    result = monitor.dispatch('allow_complete', {'contrast': contrast()})
    assert result.action is None and result.data['status'] == 'release_not_executed'
    assert monitor.crs.root_contrast['handoff']['request_id'] == 'completion-2'
    assert monitor.crs.root_contrast['surfaced'] is False


def test_local_intervention_and_wait_do_not_require_crs(tmp_path):
    monitor, _, _, _ = fixture(tmp_path)
    monitor.frame_kind = 'local'
    monitor.completion_state = lambda: None
    monitor.intervention_callback = lambda _: {
        'submission_id': 'queued-local', 'submitted_task_turn': 8,
        'submitted_cursor': 1, 'delivery': 'queued'}
    action = monitor.dispatch('intervene', {'message': 'Remember the public route.'}).action
    assert action.kind == 'local_intervened'
    assert monitor.control_echo.pending_submission['submission_id'] == 'queued-local'
    assert monitor.crs.root_contrast is None
    assert monitor.dispatch('wait', {'after_turns': 2, 'mode': 'follow'}).action.kind == 'wait'


def test_configuration_and_frozen_system_prompt(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    assert monitor.crs is not None and monitor.control_echo is not None
    assert [t['function']['name'] for t in crs_tools()] == [t['function']['name'] for t in MONITOR_TOOLS]
    client.config['monitor_adaptive_supervisory_environment'] = False
    with pytest.raises(ValueError, match='requires ASE'):
        MonitorAgent(client, workspace)
    source = Path(__file__).parents[1] / 'monitor_agent_core/ase_v0.py'
    old = subprocess.check_output(['git', 'show',
        'dfec10511bdafe97e8a0041cb95d19f5bed4de9b:GenericAgent-main/monitor_agent_core/ase_v0.py'])
    assert source.read_bytes() == old
    tree = ast.parse(source.read_text(encoding='utf-8'))
    prompt = next(node.value.value for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == 'SYSTEM_PROMPT'
                          for target in node.targets))
    assert hashlib.sha256(prompt.encode('utf-8')).hexdigest() == \
        'd1268a1c6227bdd0c02e23c65ea4f9f356717ae9cd1c8f26b265a1aa37a65648'
