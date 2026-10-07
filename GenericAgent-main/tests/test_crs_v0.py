"""Zero-model CRS-v0 release and provenance checks."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent, crs_tools
from monitor_agent_core.crs_v0 import (CRS_PUBLIC_RESULT_EXCERPT_CHARS,
                                        CRS_SURFACE_MAX_CHARS, validate_contrast)
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def fixture(tmp_path, *, rhr=False):
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
        'monitor_contrastive_release_state': True,
        'monitor_receding_horizon_release': rhr})
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
    value = {'release_blocking_state': 'The public route is absent.',
             'grounding': 'The public task requires the route.',
             'ground_refs': ['task/original_task.txt'],
             'exclusion_reason': 'The observed route result would differ if it were absent.',
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


def visible(snapshot):
    return '\n'.join(block['text'] for message in snapshot['messages']
                     for block in message['content'] if block.get('type') == 'text')


def test_schema_tools_and_first_boundary(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    assert [x['function']['name'] for x in crs_tools()] == [x['function']['name'] for x in MONITOR_TOOLS]
    assert set(crs_tools()[-1]['function']['parameters']['required']) == set(contrast())
    properties = crs_tools()[-1]['function']['parameters']['properties']
    assert 'contrast' not in properties
    assert 'contract-violating WORLD STATE' in properties['release_blocking_state']['description']
    assert 'not an alternative control action' in properties['release_blocking_state']['description']
    assert 'do not call allow_complete' in crs_tools()[-1]['function']['description']
    assert monitor.dispatch('allow_complete', {}).action is None
    assert monitor.dispatch('allow_complete', contrast(ground_refs=[])).action is None
    monitor.dcm.model_turn = 1
    first = monitor.dispatch('allow_complete', contrast())
    assert first.action is None and first.data['status'] == 'release_not_executed'
    assert monitor.crs.root_contrast['surfaced'] is False
    shown = expose(monitor, client)
    assert 'Contrastive Release State' in shown and monitor.crs.root_contrast['canonical'] in shown
    assert 'mechanical provenance only; no adequacy/support/verdict is supplied by runtime' in shown
    assert 'tool_results_json_excerpt' in shown and 'tool_result_sha256' in shown
    assert 'task_turn' in shown and 'archive_sequence' in shown
    assert 'state_digest=' + monitor.crs.root_contrast['state_digest'] in shown
    assert len(monitor.crs.render_root(monitor.root_frame_handoff)) <= CRS_SURFACE_MAX_CHARS
    assert monitor.crs.root_contrast['surfaced'] is True
    assert [r['event'] for r in events(workspace)].count('crs_surface_injected') == 1


def test_second_turn_exact_or_revised_contrast(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    assert monitor.dispatch('allow_complete', contrast()).action is None
    # Two calls in the same provider response cannot use a pending surface.
    assert monitor.dispatch('allow_complete', contrast()).action is None
    expose(monitor, client)
    monitor.dcm.model_turn = 2
    changed = contrast(release_blocking_state='A different public route is absent.')
    assert monitor.dispatch('allow_complete', changed).action is None
    assert monitor.crs.root_contrast['surfaced'] is False
    assert monitor.dispatch('allow_complete', changed).action is None
    expose(monitor, client)
    monitor.dcm.model_turn = 3
    assert monitor.dispatch('allow_complete', changed).action.kind == 'allow_complete'
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
                  'name': 'allow_complete', 'input': contrast()}
                 for n in range(calls)], {})

    monkeypatch.setattr(client, '_request_once', offline_response)
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete' and len(snapshots) == 2
    first = visible(snapshots[0])
    second = visible(snapshots[1])
    assert 'Contrastive Release State' not in first
    assert 'Contrastive Release State' in second
    assert json.dumps(contrast(), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')) in second
    assert len([r for r in events(workspace) if r['event'] == 'crs_release_attempted']) == 3
    assert len([r for r in events(workspace) if r['event'] == 'crs_confirmed']) == 1
    assert monitor.crs.root_contrast is None


def test_local_provider_schema_is_baseline_ase_and_only_root_allow_changes(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path)
    monitor.frame_kind = 'local'
    monitor.root_frame_handoff = None
    monitor.completion_state = lambda: None
    local = []

    def local_response(tools):
        local.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': 'local-wait', 'name': 'wait',
                  'input': {'after_turns': 1, 'mode': 'follow'}}], {})

    monkeypatch.setattr(client, '_request_once', local_response)
    assert monitor.review('Local').kind == 'wait'
    baseline_config = dict(client.config)
    baseline_config['monitor_contrastive_release_state'] = False
    baseline_client = MonitorProviderClient('anthropic', baseline_config)
    baseline = MonitorAgent(baseline_client, workspace)
    baseline.task_budget_state = lambda: (8, 300)
    baseline_local = []

    def baseline_response(tools):
        baseline_local.append(baseline_client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': 'baseline-wait', 'name': 'wait',
                  'input': {'after_turns': 1, 'mode': 'follow'}}], {})

    monkeypatch.setattr(baseline_client, '_request_once', baseline_response)
    assert baseline.review('Local').kind == 'wait'
    assert local[0]['tools'] == baseline_local[0]['tools']
    assert local[0]['tools'][-1]['function']['parameters'] == MONITOR_TOOLS[-1]['function']['parameters']

    monitor.completion_state = lambda: handoff
    monitor._seen_completion = handoff
    root = []

    def root_response(tools):
        root.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': 'root-allow', 'name': 'allow_complete',
                  'input': contrast()}], {})

    monkeypatch.setattr(client, '_request_once', root_response)
    # One model turn is enough to capture the root provider schema; exhaustion cannot release.
    with pytest.raises(Exception, match='exceeded'):
        monitor.review('Root', completion_pending=True, root_handoff=handoff,
                       max_turns_override=1)
    assert len(root) == 1
    assert [x['function']['name'] for x in root[0]['tools']] == [x['function']['name'] for x in MONITOR_TOOLS]
    assert root[0]['tools'][:-1] == local[0]['tools'][:-1]
    assert set(root[0]['tools'][-1]['function']['parameters']['required']) == set(contrast())
    assert 'contrast' not in local[0]['tools'][-1]['function']['parameters']['properties']


def test_identical_text_with_changed_task_book_sha_requires_new_surface(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    value = contrast(ground_refs=['monitor/reference.md'])
    monitor.dcm.model_turn = 1
    first = monitor.dispatch('allow_complete', value)
    assert first.action is None
    first_state = first.data['state_digest']
    first_contrast = first.data['contrast_sha256']
    first_visible = expose(monitor, client)
    old_sha = monitor.crs.root_contrast['provenance']['ground_refs'][0]['source_sha256']
    assert old_sha in first_visible
    workspace.write_text('monitor/reference.md', 'Revised durable public-route requirement.')
    monitor.dcm.model_turn = 2
    revised = monitor.dispatch('allow_complete', value)
    assert revised.action is None and revised.data['status'] == 'release_not_executed'
    assert revised.data['contrast_sha256'] == first_contrast
    assert revised.data['state_digest'] != first_state
    assert monitor.crs.root_contrast['surfaced'] is False
    new_sha = monitor.crs.root_contrast['provenance']['ground_refs'][0]['source_sha256']
    assert new_sha != old_sha
    second_visible = expose(monitor, client)
    assert new_sha in second_visible and revised.data['state_digest'] in second_visible
    monitor.dcm.model_turn = 3
    assert monitor.dispatch('allow_complete', value).action.kind == 'allow_complete'
    revisions = [r for r in events(workspace) if r['event'] == 'crs_revised']
    assert revisions[-1]['same_contrast'] is True


def test_historical_file_read_receipt_identity_ignores_later_workspace_change(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    monitor._audit_dialogue('tool_call', turn=1, tool_id='read-historical', name='file_read',
                            arguments=json.dumps({'path': 'task/workspace/route.py'}))
    receipt = monitor.dispatch('file_read', {'path': 'task/workspace/route.py'}).data
    monitor._audit_dialogue('tool_result', turn=1, tool_id='read-historical', data=receipt, action=None)
    locator = f'monitor/audit/dialogue.jsonl#{len(events(workspace))}'
    value = contrast(observation_refs=[locator])
    monitor.dcm.model_turn = 1
    first = monitor.dispatch('allow_complete', value)
    assert first.action is None
    expose(monitor, client)
    (workspace.task_mounts['workspace'] / 'route.py').write_text('ROUTE = False\n', encoding='utf-8')
    monitor.dcm.model_turn = 2
    confirmed = monitor.dispatch('allow_complete', value)
    assert confirmed.action.kind == 'allow_complete'
    assert receipt['sha256'] != hashlib.sha256(b'ROUTE = False\n').hexdigest()


def test_cancelled_code_run_is_visible_despite_model_success_claim(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path)
    path = workspace.private_root / 'audit/dialogue.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in [
        {'event': 'tool_call', 'tool_id': 'c1', 'review_id': 'prior', 'name': 'code_run',
         'arguments': json.dumps({'code': 'print(1)'})},
        {'event': 'tool_result', 'tool_id': 'c1', 'review_id': 'prior',
         'data': {'status': 'cancelled', 'session_id': 's1', 'cancelled': True,
                  'exit_code': None}},
    ]), encoding='utf-8')
    value = contrast(exclusion_reason='This observation was successful.',
                     observation_refs=['monitor/audit/dialogue.jsonl#2'])
    snapshots = []

    def offline_response(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        return ([{'type': 'tool_use', 'id': f'allow-{len(snapshots)}',
                  'name': 'allow_complete', 'input': value}], {})

    monkeypatch.setattr(client, '_request_once', offline_response)
    assert monitor.review('Root', completion_pending=True, root_handoff=handoff).kind == 'allow_complete'
    assert len(snapshots) == 2
    second = visible(snapshots[1])
    assert 'This observation was successful.' in second
    assert '"status":"cancelled"' in second and '"cancelled":true' in second
    assert '"session_id":"s1"' in second and 'receipt_sha256' in second
    assert 'mechanical provenance only; no adequacy/support/verdict is supplied by runtime' in second
    assert [r for r in events(workspace) if r['event'] == 'crs_confirmed']


def test_public_tool_result_excerpt_is_raw_bounded_and_visible(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    event = json.loads((workspace.evidence_root / 'public_events.jsonl').read_text(encoding='utf-8'))
    event['tool_results'][0]['content'] = 'RAW_RESULT_' + 'x' * 2000
    (workspace.evidence_root / 'public_events.jsonl').write_text(json.dumps(event) + '\n', encoding='utf-8')
    monitor.dcm.model_turn = 1
    assert monitor.dispatch('allow_complete', contrast()).action is None
    proof = monitor.crs.root_contrast['provenance']['observation_refs'][0]
    assert proof['tool_results_excerpt_truncated'] is True
    assert len(proof['tool_results_json_excerpt']) == CRS_PUBLIC_RESULT_EXCERPT_CHARS
    shown = expose(monitor, client)
    assert 'RAW_RESULT_' in shown and 'tool_results_json_characters' in shown
    assert proof['tool_result_sha256'] in shown
    assert len(monitor.crs.render_root(monitor.root_frame_handoff)) <= CRS_SURFACE_MAX_CHARS


def test_existing_and_new_observation_revision_without_required_new_measurement(tmp_path):
    monitor, client, workspace, _ = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', contrast())
    expose(monitor, client)
    monitor.dcm.model_turn = 2
    # An old completed observation is sufficient; no post-boundary tool is required.
    assert monitor.dispatch('allow_complete', contrast()).action.kind == 'allow_complete'
    monitor.dcm.begin_review('r2')
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', contrast())
    expose(monitor, client)
    monitor._audit_dialogue('tool_call', turn=2, tool_id='read-1', name='file_read',
                            arguments=json.dumps({'path': 'task/workspace/route.py',
                                                  'start': 1, 'count': 1}))
    receipt = monitor.dispatch('file_read', {'path': 'task/workspace/route.py'}).data
    monitor._audit_dialogue('tool_result', turn=2, tool_id='read-1', data=receipt, action=None)
    locator = f'monitor/audit/dialogue.jsonl#{len(events(workspace))}'
    revised = contrast(observation_refs=[locator])
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', revised).action is None
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['path'] == 'task/workspace/route.py'
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['start'] == receipt['start']
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['lines'] == receipt['lines']
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['lifecycle']['sha256'] == receipt['sha256']
    shown = expose(monitor, client)
    assert '"requested_range"' in shown and '"count":1' in shown
    assert '"path":"task/workspace/route.py"' in shown
    assert receipt['sha256'] in shown and '"truncated":false' in shown
    assert monitor.crs.root_contrast['provenance']['observation_refs'][0]['receipt_sha256'] in shown


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
    with pytest.raises(ValueError, match='source exists but is not an observation result'):
        validate_contrast(contrast(observation_refs=['task/public_events.jsonl#2']), workspace)


def test_original_task_line_range_and_actionable_invalid_ref(tmp_path):
    monitor, _, workspace, _ = fixture(tmp_path)
    (workspace.evidence_root / 'original_task.txt').write_text(
        ''.join(f'Public line {n}\n' for n in range(1, 131)), encoding='utf-8')
    ground = validate_contrast(contrast(ground_refs=['task/original_task.txt lines 121-127']),
                               workspace)[2]['ground_refs'][0]
    assert ground['locator'] == 'task/original_task.txt'
    assert ground['submitted_ref'] == 'task/original_task.txt lines 121-127'
    assert (ground['line_start'], ground['line_end']) == (121, 127)
    monitor._audit_dialogue('tool_call', turn=1, tool_id='read-1', name='file_read',
                            arguments=json.dumps({'path': 'task/workspace/route.py'}))
    result = monitor.dispatch('file_read', {'path': 'task/workspace/route.py'}).data
    monitor._audit_dialogue('tool_result', turn=1, tool_id='read-1', data=result, action=None)
    with pytest.raises(ValueError) as exc:
        validate_contrast(contrast(observation_refs=['not-an-observation']), workspace, 'r1')
    error = str(exc.value)
    assert "observation_refs[0]" in error and 'not-an-observation' in error
    assert 'task/public_events.jsonl#cursor' in error and 'obs:read:' in error


def test_scripted_root_code_receipt_handle_flat_proposal_and_confirmation(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path)
    (workspace.evidence_root / 'original_task.txt').write_text(
        ''.join(f'Public line {n}\n' for n in range(1, 131)), encoding='utf-8')
    output_path = 'monitor/audit/commands/session-1/output.log'
    monkeypatch.setattr(monitor.analysis, 'start', lambda *args, **kwargs: {
        'status': 'success', 'session_id': 'session-1', 'exit_code': 0,
        'output_path': output_path})
    snapshots = []
    submitted = []

    def offline_response(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        ordinal = len(snapshots)
        if ordinal == 1:
            return ([{'type': 'tool_use', 'id': 'code-1', 'name': 'code_run',
                      'input': {'code': 'print(1)', 'type': 'python'}}], {})
        if ordinal == 2:
            shown = visible(snapshots[-1])
            import re
            handle = re.search(r'obs:code:[0-9a-f]{24}', shown).group()
            submitted.append(contrast(ground_refs=['task/original_task.txt lines 121-127'],
                                      observation_refs=[handle]))
        return ([{'type': 'tool_use', 'id': f'allow-{ordinal}', 'name': 'allow_complete',
                  'input': submitted[0]}], {})

    monkeypatch.setattr(client, '_request_once', offline_response)
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'allow_complete' and len(snapshots) == 3
    assert 'CRS-citable observation receipts' in visible(snapshots[1])
    assert output_path in visible(snapshots[1])
    assert 'Contrastive Release State' in visible(snapshots[2])
    proof = [e for e in events(workspace) if e['event'] == 'crs_proposed'][0]
    assert proof['observation_refs'][0]['locator'].startswith('monitor/audit/dialogue.jsonl#')
    assert proof['observation_refs'][0]['submitted_ref'] == submitted[0]['observation_refs'][0]
    alias = validate_contrast(contrast(observation_refs=[output_path]), workspace)[2]
    assert alias['observation_refs'][0]['locator'] == proof['observation_refs'][0]['locator']
    assert len([e for e in events(workspace) if e['event'] == 'crs_confirmed']) == 1


def test_scripted_root_intervention_requires_no_crs_and_arms_no_release(tmp_path, monkeypatch):
    monitor, client, workspace, handoff = fixture(tmp_path)
    monitor.intervention_callback = lambda message: {'submission_id': 'queued-root',
                                                      'delivery': 'queued'}
    monkeypatch.setattr(client, '_request_once', lambda tools: (
        [{'type': 'tool_use', 'id': 'intervene-1', 'name': 'intervene',
          'input': {'message': 'The public route is absent.'}}], {}))
    action = monitor.review('Root', completion_pending=True, root_handoff=handoff)
    assert action.kind == 'root_intervened'
    assert monitor.crs.root_contrast is None
    assert not [e for e in events(workspace) if e['event'] == 'crs_proposed']


def test_intervention_stale_handoff_and_review_end_abandon(tmp_path):
    monitor, client, workspace, handoff = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', contrast())
    expose(monitor, client)
    monitor.intervention_callback = lambda _: {'submission_id': 'queued', 'delivery': 'queued'}
    assert monitor.dispatch('intervene', {'message': 'Recheck the public route.'}).action.kind == 'root_intervened'
    assert monitor.crs.root_contrast is None
    monitor.dcm.begin_review('r2')
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', contrast())
    handoff['generation'] = 2
    handoff['request_id'] = 'completion-2'
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', contrast()).action is None
    assert monitor.crs.root_contrast['handoff']['generation'] == 2
    monitor.dcm.end_review('review_exhausted')
    assert monitor.crs.root_contrast is None
    assert not [r for r in events(workspace) if r['event'] == 'crs_confirmed']


def test_provider_failure_and_review_error_cannot_release(tmp_path):
    monitor, _, _, _ = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', contrast())
    monitor.dcm.end_review('error')
    assert monitor.crs.root_contrast is None
    monitor.dcm.begin_review('r2')
    monitor.dcm.model_turn = 2
    assert monitor.dispatch('allow_complete', contrast()).action is None


def test_new_handoff_does_not_inherit_surfaced_contrast(tmp_path):
    monitor, client, _, handoff = fixture(tmp_path)
    monitor.dcm.model_turn = 1
    monitor.dispatch('allow_complete', contrast())
    expose(monitor, client)
    handoff.update(request_id='completion-2', generation=2)
    monitor.dcm.model_turn = 2
    result = monitor.dispatch('allow_complete', contrast())
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
