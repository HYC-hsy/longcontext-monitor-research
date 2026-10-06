"""Stage 1 runner audit with local fake transport only; no scientific call."""

import json
import shutil
from collections import Counter

import pytest

from stage1_blind_export import export, load_secret_map
from stage1_plan import (CASES, CONDITIONS, EXPECTED_MODEL, FIXTURE_COMMIT, PANEL,
                         PROFILE, REPLICATES, canonical, frozen_fixture_manifest,
                         generate_plan, sha)
from stage1_runner import (PLAN, REPO, parse_action, real_transport, require_authorization,
                           semantic_request, validate_plan, verify_provider_source,
                           verify_effective_profile)


def synthetic_secret_map(tmp_path):
    path = tmp_path / 'synthetic_test_blind_map.json'
    pairs = [{'case_id': case, 'replicate': rep,
              'A': ('current' if (index + rep) % 3 == 0 else 'constitution')}
             for index, case in enumerate(CASES) for rep in REPLICATES]
    path.write_bytes(canonical({'schema_version': 'stage1-secret-blind-map/1',
                                'pairs': pairs}) + b'\n')
    return path, sha(path.read_bytes())


def fake_profile(**changes):
    value = {'apikey': 'FAKE_TEST_ONLY', 'apibase': 'http://127.0.0.1:9',
             'model': EXPECTED_MODEL, 'provider': 'anthropic', 'api_mode': 'messages',
             'temperature': 1, 'thinking_type': 'adaptive', 'max_tokens': 8192,
             'max_retries': 8, 'transport_route': 'monitor'}
    value.update(changes)
    return value


def test_exact_frozen_54_call_allocation_and_order():
    manifest = frozen_fixture_manifest(REPO)
    plan = validate_plan()
    assert plan == generate_plan(manifest)
    assert plan['fixture_commit'] == FIXTURE_COMMIT
    assert plan['execution_authorized'] is False
    assert plan['planned_logical_calls'] == len(plan['trials']) == 54
    assert len({row['trial_id'] for row in plan['trials']}) == 54
    assert set(row['case_id'] for row in plan['trials']) == set(CASES)
    assert Counter((row['case_id'], row['condition']) for row in plan['trials']) == {
        (case, condition): 3 for case in CASES for condition in CONDITIONS}
    assert [row['ordinal'] for row in plan['trials']] == list(range(1, 55))
    assert all(row['status'] == 'not_started' for row in plan['trials'])
    for index in range(0, 54, 2):
        first, second = plan['trials'][index:index + 2]
        assert (first['case_id'], first['replicate']) == (second['case_id'], second['replicate'])
        assert {first['condition'], second['condition']} == set(CONDITIONS)
    assert plan['profile'] == PROFILE and plan['expected_model'] == EXPECTED_MODEL


def test_paired_requests_only_differ_in_cognitive_core_and_read_no_gold(monkeypatch):
    import pathlib
    original = pathlib.Path.read_bytes

    def guarded_read(path):
        if 'sealed' in path.parts:
            raise AssertionError('Request path attempted to read sealed gold')
        return original(path)

    monkeypatch.setattr(pathlib.Path, 'read_bytes', guarded_read)
    plan = validate_plan()
    for index in range(0, 54, 2):
        first, second = plan['trials'][index:index + 2]
        a, a_raw, a_sha = semantic_request(first)
        b, b_raw, b_sha = semantic_request(second)
        assert a['messages'] == b['messages'] and a['tools'] == b['tools']
        assert a['system'].split('\n\n', 1)[0] == b['system'].split('\n\n', 1)[0]
        assert a['system'] != b['system'] and a_raw != b_raw and a_sha != b_sha
        assert len(a['messages']) == 1
        names = [tool['function']['name'] for tool in a['tools']]
        assert names == (['wait', 'intervene'] if first['frame'] == 'local' else
                         ['wait', 'intervene', 'allow_complete'])


@pytest.mark.parametrize('blocks,frame,expected', [
    ([{'type': 'tool_use', 'name': 'wait', 'input': {}}], 'local', 'wait'),
    ([{'type': 'tool_use', 'name': 'intervene', 'input': {'message': 'exact text'}}],
     'local', 'intervene'),
    ([{'type': 'tool_use', 'name': 'allow_complete', 'input': {}}], 'root', 'allow_complete'),
    ([], 'local', 'invalid'),
    ([{'type': 'text', 'text': 'no tool'}], 'root', 'invalid'),
    ([{'type': 'tool_use', 'name': 'wait', 'input': {}},
      {'type': 'tool_use', 'name': 'intervene', 'input': {'message': 'x'}}], 'local', 'invalid'),
    ([{'type': 'tool_use', 'name': 'file_read', 'input': {}}], 'root', 'invalid'),
    ([{'type': 'tool_use', 'name': 'allow_complete', 'input': {}}], 'local', 'invalid'),
    ([{'type': 'tool_use', 'name': 'wait', 'input': {'after_turns': 1}}], 'local', 'invalid'),
    ([{'type': 'tool_use', 'name': 'intervene', 'input': {'message': 4}}], 'local', 'invalid'),
    ([{'type': 'tool_use', 'name': 'intervene', 'input': {'_raw': 'broken'}}], 'local', 'invalid'),
])
def test_single_action_protocol_no_repair(blocks, frame, expected):
    result = parse_action(blocks, frame)
    assert result['selected_action'] == expected
    if expected == 'intervene':
        assert result['intervention_message'] == 'exact text'
    if expected == 'invalid':
        assert result['invalid_reason']


def test_transport_retry_resends_exact_payload_with_local_fake_service(monkeypatch):
    import requests
    import sys
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    from monitor_agent_core import provider

    request, _, _ = semantic_request(validate_plan()['trials'][0])
    payloads = []

    class Response:
        status_code = 200

        def __enter__(self): return self
        def __exit__(self, *_): return False
        def close(self): pass

        def iter_lines(self):
            events = [
                {'type': 'message_start', 'message': {'id': 'fake-response-id',
                                                    'usage': {'input_tokens': 2}}},
                {'type': 'content_block_start', 'content_block': {
                    'type': 'tool_use', 'id': 'fake-tool-id', 'name': 'wait'}},
                {'type': 'content_block_delta', 'delta': {
                    'type': 'input_json_delta', 'partial_json': '{}'}},
                {'type': 'content_block_stop'},
                {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'},
                 'usage': {'output_tokens': 3}},
                {'type': 'message_stop'},
            ]
            for event in events:
                yield b'data: ' + json.dumps(event).encode('utf-8')

    def fake_post(*_args, **kwargs):
        payloads.append(canonical(kwargs['json']))
        if len(payloads) == 1:
            raise requests.Timeout('synthetic first attempt timeout')
        return Response()

    monkeypatch.setattr(provider.requests, 'post', fake_post)
    import stage1_runner
    monkeypatch.setattr(stage1_runner.time, 'sleep', lambda *_: None)
    profile = fake_profile()
    pre_send = []
    result = real_transport(request, profile, 'f' * 64,
                            lambda payload, effective: pre_send.append((payload, effective)))
    assert result['error'] is None
    assert len(pre_send) == 1 and pre_send[0][0]['model'] == EXPECTED_MODEL
    assert len(payloads) == 2 and payloads[0] == payloads[1]
    assert len(result['attempt_payload_sha256']) == 2
    assert result['attempt_payload_sha256'][0] == result['attempt_payload_sha256'][1]
    assert result['response_metadata']['provider_message_id'] == 'fake-response-id'
    assert result['response_metadata']['stop_reason'] == 'tool_use'
    assert parse_action(result['blocks'], 'local')['selected_action'] == 'wait'
    assert len(result['raw_response_stream']['attempts']) == 2
    assert result['raw_response_stream']['attempts'][0] == []
    assert len(result['raw_response_stream']['attempts'][1]) == 6
    assert 'FAKE_TEST_ONLY' not in json.dumps(result)


def test_complete_zero_tool_response_is_invalid_not_retried(monkeypatch):
    import sys
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    from monitor_agent_core import provider
    request, _, _ = semantic_request(validate_plan()['trials'][0])
    calls = []

    class EmptyResponse:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *_): return False
        def close(self): pass
        def iter_lines(self):
            for event in ({'type': 'message_start', 'message': {'id': 'empty-complete'}},
                          {'type': 'message_stop'}):
                yield b'data: ' + json.dumps(event).encode('utf-8')

    def fake_post(*_args, **_kwargs):
        calls.append(1)
        return EmptyResponse()

    monkeypatch.setattr(provider.requests, 'post', fake_post)
    profile = fake_profile()
    result = real_transport(request, profile, 'f' * 64)
    assert result['error'] is None and result['blocks'] == []
    assert len(calls) == 1 and len(result['request_attempts']) == 1
    assert parse_action(result['blocks'], 'local')['selected_action'] == 'invalid'


def test_blind_export_is_separate_and_contains_no_condition_identity(tmp_path):
    records = []
    for row in validate_plan()['trials']:
        records.append({**row, 'status': 'response_recorded',
                        'selected_action': 'wait', 'intervention_message': None,
                        'raw_response_blocks': [{'type': 'text', 'text': 'synthetic output'}]})
    secret_path, commitment = synthetic_secret_map(tmp_path)
    blind_path, map_path = export(records, tmp_path, secret_path, commitment)
    blind = json.loads(blind_path.read_bytes())
    mapping = json.loads(map_path.read_bytes())
    assert len(blind['pairs']) == 27 and len(mapping['mapping']) == 54
    assert 'current' not in blind_path.read_text(encoding='utf-8')
    assert 'constitution' not in blind_path.read_text(encoding='utf-8')
    assert 'condition' not in blind_path.read_text(encoding='utf-8')
    assert 'expected_action' not in blind_path.read_text(encoding='utf-8')
    assert 'current' in map_path.read_text(encoding='utf-8')
    assert 'constitution' in map_path.read_text(encoding='utf-8')
    assert blind_path.parent.name == 'blind'
    assert map_path.parent.name == 'sealed_condition_map'
    assigned = load_secret_map(secret_path, commitment)
    for pair in blind['pairs']:
        case, rep = pair['case_id'], pair['replicate']
        revealed = [item for item in mapping['mapping']
                    if item['case_id'] == case and item['replicate'] == rep]
        assert len(revealed) == 2
        for item in revealed:
            assert item['condition'] == assigned[(case, rep)][item['response_label']]
            assert item['trial_id'] == next(row['trial_id'] for row in validate_plan()['trials']
                                             if row['case_id'] == case and row['replicate'] == rep
                                             and row['condition'] == item['condition'])


def test_secret_map_mutation_refused_and_public_order_not_mapping(tmp_path):
    plan = validate_plan()
    secret_path, commitment = synthetic_secret_map(tmp_path)
    raw = secret_path.read_bytes()
    mutated = tmp_path / 'mutated.json'
    mutated.write_bytes(raw[:-2] + bytes([raw[-2] ^ 1]) + raw[-1:])
    with pytest.raises(ValueError, match='commitment'):
        load_secret_map(mutated, commitment)
    # The public plan exposes only a commitment; no A/B assignment or rule.
    public = PLAN.read_text(encoding='utf-8')
    assert '"A"' not in public and '"B"' not in public
    assert 'blind_map_commitment_sha256' in public
    assert 'first condition is Response A' not in public


def test_provider_source_and_effective_semantics_gates(tmp_path):
    identity = verify_provider_source()
    assert identity['git_blob'] == 'd27ef568a3e7b7d2a49563145a8f7b1a26830692'
    copy = tmp_path / 'provider.py'
    copy.write_bytes((REPO / 'GenericAgent-main/monitor_agent_core/provider.py').read_bytes() + b'X')
    with pytest.raises(ValueError, match='provider source'):
        verify_provider_source(provider_path=copy)
    import sys
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    from monitor_agent_core.provider import MonitorProviderClient
    assert verify_effective_profile(fake_profile(), MonitorProviderClient(PROFILE, fake_profile()))
    changed = fake_profile(max_tokens=4096)
    with pytest.raises(ValueError, match='profile semantics'):
        verify_effective_profile(changed, MonitorProviderClient(PROFILE, changed))


def test_mutated_provider_refused_by_execution_gate_before_transport(tmp_path, monkeypatch):
    import stage1_runner
    copy = tmp_path / 'provider.py'
    copy.write_bytes((REPO / 'GenericAgent-main/monitor_agent_core/provider.py').read_bytes() + b'X')
    monkeypatch.setattr(stage1_runner, 'require_authorization', lambda *_: {})
    monkeypatch.setattr(stage1_runner, 'verify_provider_source',
                        lambda: verify_provider_source(provider_path=copy))
    monkeypatch.setattr(stage1_runner, 'real_transport',
                        lambda *_args, **_kwargs: pytest.fail('network path reached'))
    output = tmp_path / 'unused_output'
    with pytest.raises(ValueError, match='provider source'):
        stage1_runner.run_authorized(PLAN, tmp_path / 'fake_profile.json',
                                     tmp_path / 'fake_auth.json', output)
    assert not output.exists()


def test_fixture_mutations_fail_before_provider_path(tmp_path):
    for relative in ('cases/C01/packet.json', 'prompts/panel_shell.txt',
                     'prompts/current_cognitive_core.txt',
                     'prompts/constitution_cognitive_core.txt',
                     'preview_runner.py'):
        panel = tmp_path / relative.replace('/', '_')
        shutil.copytree(PANEL, panel, ignore=shutil.ignore_patterns('__pycache__'))
        target = panel / relative
        target.write_bytes(target.read_bytes() + b'X')
        with pytest.raises(ValueError):
            frozen_fixture_manifest(REPO, panel)


def test_no_execution_authority_is_shipped_and_wrong_auth_refused(tmp_path):
    assert not (PANEL / 'stage1' / 'AUTHORIZATION.json').exists()
    path = tmp_path / 'not_authorized.json'
    path.write_text(json.dumps({'execution_authorized': False}), encoding='utf-8')
    private = tmp_path / 'fake_profile.json'
    private.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match='authorization'):
        require_authorization(path, PLAN, private)


def test_production_imports_are_not_modified_by_runner_commit():
    runner_source = (PANEL / 'stage1_runner.py').read_text(encoding='utf-8')
    assert 'sealed/gold.json' not in runner_source
    assert 'from stage1_score_offline' not in runner_source
    assert 'monitor_agent_core.provider import MonitorProviderClient' in runner_source
    assert 'if __name__' in runner_source
