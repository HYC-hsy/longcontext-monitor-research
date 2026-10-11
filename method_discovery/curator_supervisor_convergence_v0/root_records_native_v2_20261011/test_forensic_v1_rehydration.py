"""Read-only zero-model compatibility check of the archived Kitex-S v1 failure."""

import copy
import json
from pathlib import Path

import pytest

from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.root_records_v1 import canonical, digest
from monitor_agent_core.root_records_native_v2 import project

from method_discovery.curator_supervisor_convergence_v0.root_records_native_v2_20261011.forensic_v1_rehydration import rehydrate


AUDIT = (Path(__file__).resolve().parents[1] /
         'real_task_effect_pilot_preflight_20261010/live_batch2_20261011/'
         'arms/kitex_s/monitor/audit')


def test_authenticated_nested_v1_records_restore_native_exchange_cuts():
    source = json.loads((AUDIT / 'provider_history.json').read_text(encoding='utf-8'))
    original = copy.deepcopy(source)
    restored, lineage = rehydrate(source, AUDIT / 'root_projections')
    assert source == original and len(source) == 2
    assert len(lineage['lineage']) == 5
    assert lineage['tool_pairs'] == 189
    assert len(restored) == 250
    projected, manifest, raw = project(restored)
    assert raw == canonical(restored) and projected == restored
    assert manifest['applied'] is False  # old removed reasoning is not reintroduced
    client = MonitorProviderClient('claude', {
        'apikey': 'offline', 'apibase': 'https://invalid.invalid',
        'model': 'claude', 'context_win': 200000})
    client.restore_history(projected)
    assert client._exchange_boundaries()
    assert len(client._exchange_boundaries()) == 101
    assert not any(block['type'] == 'tool_use' for message in source
                   for block in message['content'])
    assert client.history_measure()['characters'] == 630786
    assert client.history_char_limit == 700000 and client.history_target_chars == 574000


def test_ledger_like_text_without_archive_provenance_fails():
    source = json.loads((AUDIT / 'provider_history.json').read_text(encoding='utf-8'))
    source[0]['content'][0]['text'] += 'changed'
    with pytest.raises(ValueError, match='Unproven'):
        rehydrate(source, AUDIT / 'root_projections')


def test_archive_manifest_tamper_fails_without_source_rewrite(tmp_path):
    source = json.loads((AUDIT / 'provider_history.json').read_text(encoding='utf-8'))
    for original in (AUDIT / 'root_projections').iterdir():
        if original.is_dir():
            target = tmp_path / original.name
            target.mkdir()
            for name in ('source.json', 'projected_history.json', 'manifest.json', 'committed.json'):
                (target / name).write_bytes((original / name).read_bytes())
    manifest = next(tmp_path.glob('*/manifest.json'))
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['removed_blocks'] += 1
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='Unauthenticated'):
        rehydrate(source, tmp_path)
