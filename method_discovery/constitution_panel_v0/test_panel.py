"""Zero-model integrity checks for the frozen public snapshot package."""

import hashlib
import json
from pathlib import Path

import pytest

from build_panel import CASES, SOURCE_COMMIT, git_bytes, load_public_task, public_turns
from preview_runner import PANEL, assemble, control_tools, load_inputs, preview


REPO = PANEL.parents[1]
MANIFEST = json.loads((PANEL / 'manifest.json').read_text(encoding='utf-8'))
GOLD = json.loads((PANEL / 'sealed' / 'gold.json').read_text(encoding='utf-8'))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def built():
    return [row for row in MANIFEST['cases'] if row['status'] == 'BUILT_FOR_MAIN_AUDIT']


def test_all_nine_cases_have_provenance_and_explicit_status():
    assert len(MANIFEST['cases']) == len(CASES) == 9
    assert {row['case_id'] for row in MANIFEST['cases']} == {item[0] for item in CASES}
    for row in MANIFEST['cases']:
        provenance = json.loads((PANEL / 'cases' / row['case_id'] / 'provenance.json').read_text(
            encoding='utf-8'))
        assert provenance['status'] == row['status']
        assert provenance['cutoff_turn'] == row['cutoff_turn']
        if row['status'] == 'UNBUILDABLE':
            assert row['reason'] and not (PANEL / 'cases' / row['case_id'] / 'packet.json').exists()
        else:
            assert row['packet_characters'] > 0 and row['full_public_task_recovered']


def test_packets_are_exact_public_turns_and_do_not_import_sealed_decisions():
    assert set(GOLD['cases']) == {item[0] for item in CASES}
    for row in built():
        case = row['case_id']
        packet_path = PANEL / 'cases' / case / 'packet.json'
        raw = packet_path.read_bytes()
        packet = json.loads(raw)
        provenance = json.loads((packet_path.parent / 'provenance.json').read_text(encoding='utf-8'))
        assert digest(raw) == row['packet_sha256'] == provenance['packet_sha256']
        assert set(packet) == {'case_id', 'frame', 'public_task', 'prior_public_control',
                               'public_observations', 'decision_prompt'}
        assert packet['case_id'] == case and packet['prior_public_control'] is None
        assert packet['decision_prompt'].startswith('Decide the next supervisory control action')
        assert packet['public_task'].encode('utf-8') == (
            packet_path.parent / 'source_extracts' / 'public_task.txt').read_bytes()
        observation_source = provenance['public_observation_source']
        transcript = git_bytes(REPO, SOURCE_COMMIT, observation_source['source_path'])
        expected = public_turns(transcript, row['cutoff_turn'])
        assert [item['content'] for item in packet['public_observations']] == [x[1] for x in expected]
        assert [item['task_turn'] for item in packet['public_observations']] == [x[0] for x in expected]
        assert all(item['kind'] == 'task_online_turn' for item in packet['public_observations'])
        assert max(x['task_turn'] for x in packet['public_observations']) <= row['cutoff_turn']
        assert provenance['public_observation_source']['max_source_event_turn_included'] <= row['cutoff_turn']
        assert (packet_path.parent / 'source_extracts' / 'task_turns_through_cutoff.txt').read_bytes() == \
            ''.join(x[1] for x in expected).encode('utf-8')
        sealed = GOLD['cases'][case]
        serialized = raw.decode('utf-8')
        assert sealed['sealed_decision'] not in serialized
        for key in ('sealed_diagnosis', 'sealed_release_condition', 'sealed_rationale'):
            value = sealed.get(key)
            if isinstance(value, str) and len(value) > 24:
                assert value not in serialized


def test_no_hidden_verifier_solution_sources_or_future_events():
    forbidden = ('native verifier', 'hidden test', 'reference solution', '/solution/',
                 'test.sh', 'solve.sh')
    for row in built():
        case = row['case_id']
        packet = (PANEL / 'cases' / case / 'packet.json').read_text(encoding='utf-8').lower()
        assert not any(marker in packet for marker in forbidden)
        provenance = json.loads((PANEL / 'cases' / case / 'provenance.json').read_text(
            encoding='utf-8'))
        paths = [provenance['public_task_source']['source_path'],
                 provenance['public_observation_source']['source_path']]
        assert all('/tests/' not in path.replace('\\', '/').lower() and
                   '/solution/' not in path.replace('\\', '/').lower() for path in paths)
        assert all(item['task_turn'] <= row['cutoff_turn']
                   for item in provenance['public_observations'])


def test_manifest_records_source_hashes_and_task_instruction_identity():
    assert MANIFEST['source_archive_commit'] == SOURCE_COMMIT
    assert MANIFEST['execution_authorized'] is False
    for path, expected in MANIFEST['source_hashes'].items():
        if path.startswith('research_collaboration_private/'):
            assert digest(git_bytes(REPO, SOURCE_COMMIT, path)) == expected
        elif path == 'prompts/current.txt':
            assert digest((PANEL / path).read_bytes()) == expected
        elif path.startswith('public_instruction:'):
            matches = [json.loads((PANEL / 'cases' / row['case_id'] / 'provenance.json').read_text(
                encoding='utf-8')) for row in built() if row['task_source'] == path.split(':', 1)[1]]
            assert matches and all(item['public_task_source']['source_sha256'] == expected
                                   for item in matches)
        else:
            raise AssertionError(f'Unexpected source manifest key: {path}')


def test_abstract_control_surface_and_prompt_only_difference():
    assert [x['function']['name'] for x in control_tools('local')] == ['wait', 'intervene']
    assert [x['function']['name'] for x in control_tools('root')] == [
        'wait', 'intervene', 'allow_complete']
    for row in built():
        packet, current = load_inputs(row['case_id'], 'current')
        first = assemble(packet, current)
        second = assemble(packet, 'FROZEN_CANDIDATE_FIXTURE_TEXT')
        assert first['messages'] == second['messages'] and first['tools'] == second['tools']
        assert first['system'] != second['system']
        assert [x['function']['name'] for x in first['tools']] == (
            ['wait', 'intervene'] if row['frame'] == 'local' else
            ['wait', 'intervene', 'allow_complete'])


def test_runner_is_preview_only_and_never_reads_sealed_or_network(tmp_path, monkeypatch):
    import socket
    monkeypatch.setattr(socket, 'socket', lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError('network path was invoked')))
    output = tmp_path / 'preview.json'
    value = preview('C09', 'current', output)
    assert digest(output.read_bytes()) == value
    assert 'sealed' not in output.read_text(encoding='utf-8').lower()
    with pytest.raises(ValueError, match='UNBUILDABLE'):
        load_inputs('C07', 'current')
    with pytest.raises(ValueError, match='not been frozen'):
        load_inputs('C09', 'constitution')
    with pytest.raises(ValueError):
        preview('C09', 'current', PANEL / 'sealed' / 'forbidden.json')


def test_missing_public_task_fails_instead_of_generating_summary(tmp_path):
    with pytest.raises((OSError, FileNotFoundError)):
        load_public_task(tmp_path, 'rat022')
