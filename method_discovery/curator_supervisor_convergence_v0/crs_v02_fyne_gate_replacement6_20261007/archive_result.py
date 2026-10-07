"""Archive one completed CRS-v0.2 Fyne run without model or verifier execution."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import archive_result as inherited


ROOT = Path(__file__).resolve().parent
RUN_ID = 'crs-v02-fyne-mechanism-gate-b-only-r1-infra-replacement-6'
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_v02_fyne_mechanism_gate')
DESTINATION = ROOT / 'archive' / 'r1'


def rows(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def interface_index():
    dialogue = rows(DESTINATION / 'monitor/audit/dialogue.jsonl')
    named = [dict(event, locator=f'monitor/audit/dialogue.jsonl#{number}')
             for number, event in enumerate(dialogue, 1)]
    crs = [row for row in named if str(row.get('event', '')).startswith('crs_')]
    calls = [row for row in named if row.get('event') == 'tool_call'
             and row.get('name') == 'allow_complete']
    errors = []
    call_ids = {row.get('tool_id') for row in calls}
    for row in named:
        if row.get('event') == 'tool_result' and row.get('tool_id') in call_ids:
            data = row.get('data')
            if isinstance(data, dict) and data.get('status') == 'error':
                errors.append(row)
    contexts = [row for row in named if row.get('event') == 'ase_context_injected']
    citable = [row for row in named if row.get('event') == 'crs_citable_observations_prepared']
    model_inputs = [row for row in named if row.get('event') == 'model_input']
    output = {
        'schema': 'crs-v02-interface-mechanical-index/1',
        'run_id': RUN_ID,
        'semantic_scoring': None,
        'root_allow_complete_calls': calls,
        'crs_events': crs,
        'crs_citable_observation_surfaces': citable,
        'context_exposure_receipts': [row for row in contexts if row.get('frame') == 'root'],
        'crs_validation_errors': errors,
        'provider_model_input_locators': [row['locator'] for row in model_inputs],
        'provider_request_raw_source': 'bridge/gateway_control_raw.zip',
        'provider_request_raw_sha256': raw.digest(DESTINATION / 'bridge/gateway_control_raw.zip')
            if (DESTINATION / 'bridge/gateway_control_raw.zip').is_file() else None,
    }
    request_counts = {'total': 0, 'monitor': 0, 'task': 0,
                      'root_flat_crs_schema': 0, 'local_ordinary_schema': 0,
                      'model_input_citable_handle': 0,
                      'model_input_citable_surface': 0,
                      'model_input_crs_state_digest': 0,
                      'model_input_crs_surface': 0}
    with zipfile.ZipFile(DESTINATION / 'bridge/gateway_control_raw.zip') as zipped:
        for name in zipped.namelist():
            if not name.endswith('.request.json'):
                continue
            request = json.loads(zipped.read(name))
            request_counts['total'] += 1
            tools = request.get('tools') or []
            allow = next((tool for tool in tools if tool.get('name') == 'allow_complete'), None)
            if allow is None:
                request_counts['task'] += 1
                continue
            request_counts['monitor'] += 1
            allow_schema = json.dumps(allow, ensure_ascii=False)
            request_counts['root_flat_crs_schema' if 'release_blocking_state' in allow_schema
                           else 'local_ordinary_schema'] += 1
            body = json.dumps({'system': request.get('system'),
                               'messages': request.get('messages')}, ensure_ascii=False)
            for key, needle in (
                ('model_input_citable_handle', 'obs:code:'),
                ('model_input_citable_surface', 'CRS-citable observation receipts'),
                ('model_input_crs_state_digest', 'state_digest'),
                ('model_input_crs_surface', 'Contrastive Release State'),
            ):
                request_counts[key] += needle in body
    output['provider_request_visibility_counts'] = request_counts
    raw.write(DESTINATION / 'CRS_V02_INTERFACE_INDEX.json', output)
    summary_path = DESTINATION / 'MECHANICAL_SUMMARY.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary['condition'] = 'crs_v02_b_only'
    summary['crs_v02_mechanics'] = {
        'root_allow_complete_calls': len(calls),
        'crs_events': {event: sum(row['event'] == event for row in crs)
                       for event in sorted({row['event'] for row in crs})},
        'crs_citable_observation_surfaces': len(citable),
        'crs_validation_errors': len(errors),
        'provider_model_inputs': len(model_inputs),
        'interface_index_sha256': raw.digest(DESTINATION / 'CRS_V02_INTERFACE_INDEX.json'),
    }
    raw.write(summary_path, summary)


def main():
    manifest = json.loads((CAMPAIGN / 'runs' / RUN_ID / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('run_id') != RUN_ID or manifest.get('valid') is not True:
        raise RuntimeError('Expected exactly this completed, valid trial')
    inherited.RUN_ID = RUN_ID
    inherited.ROOT = ROOT
    inherited.CAMPAIGN = CAMPAIGN
    inherited.DESTINATION = DESTINATION
    inherited.STAGING = Path(r'E:\crs_v02_fyne_archive_stage_r6')
    inherited.EXTRACTION = Path(r'E:\crs_fyne_gate_v02_private_20261007\final_workspace_extract_r6')
    inherited.main()
    interface_index()
    print(json.dumps({'archive': str(DESTINATION),
                      'interface_index': str(DESTINATION / 'CRS_V02_INTERFACE_INDEX.json')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
