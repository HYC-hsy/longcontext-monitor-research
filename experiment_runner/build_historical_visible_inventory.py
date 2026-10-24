"""Read-only, bounded local inventory of real runs and public visible packages.

This is an audit aid, not a claim that every historical filesystem was searched.
The selected top-level prefixes and excluded active run root are recorded in output.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_visible_audit import canonical


REPO = Path(__file__).resolve().parents[1]
D = REPO / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
PREFIXES = {
    'LongContext': ('pos', 'pma', 'gap', 'stateful', 'egv', 'candidate', 'source_memory', 'sr1'),
    'drive': ('ga-real', 'pma_d1', 'pma12_native', 'pma-harbor'),
}
EXCLUDED = set()  # only ended real episodes with live_result are included
GA_SOURCE = {
    'pma-1792c5ce7df34858': '66705fbba0771788f336884b433c9cb7dfe2372f',
    'pma-a927e53b0aef4e8e': 'f4f0eaafd412f91392b3f806f452b410245b924d',
}
PUBLIC_SINGLE = {
    'pma-1792c5ce7df34858': 'experiment_runner/ga_only_sqlite_visible_20261025',
    'pma-a927e53b0aef4e8e': 'experiment_runner/ga_only_sqlite_denied_visible_20261025',
    'pma-d1847af4750941c0': str((D / 'gap_direct_real_visible_20261022').relative_to(REPO)).replace('\\', '/'),
    'pma-b51303f481d04569': str((D / 'gap_live_sqlite_visible_20261022').relative_to(REPO)).replace('\\', '/'),
    'pma-b39bcc4a6c44456a': str((D / 'gap_prompt_visible_audit_final_20261022').relative_to(REPO)).replace('\\', '/'),
}


def _public_packages() -> tuple[dict[str, dict], list[str]]:
    found = {}
    checked = []
    for name in ('pma_gap_batch20_20261023', 'pma_gap_repeat5_20261025'):
        base = D / 'evidence' / name
        if not base.is_dir():
            continue
        checked.append(str(base.relative_to(REPO)).replace('\\', '/'))
        for directory in base.iterdir():
            identity = directory / 'IDENTITY.json'
            index = directory / 'INDEX.json'
            if not identity.is_file() or not index.is_file():
                continue
            record = json.loads(identity.read_bytes())
            items = {item['public'] for item in json.loads(index.read_bytes())['files']}
            found[record['run_id']] = {
                'path': str(directory.relative_to(REPO)).replace('\\', '/'),
                'source_sha': record.get('executed_code_commit'),
                'task_visible': 'task_events.jsonl.gz' in items,
                'aux_visible': 'gap_visible_transport.jsonl.gz' in items,
                'memory_visible': 'memory_payload.jsonl.gz' in items,
                'evaluation_visible': 'IDENTITY.json' in {p.name for p in directory.iterdir()},
                'reminder_linked': ('task_events.jsonl.gz' in items and
                                    'gap_visible_transport.jsonl.gz' in items),
                'package_kind': name,
            }
    for run_id, path in PUBLIC_SINGLE.items():
        directory = REPO / path
        if not (directory / 'INDEX.json').is_file():
            continue
        checked.append(path)
        files = {p.name for p in directory.iterdir() if p.is_file()}
        found[run_id] = {
            'path': path, 'source_sha': GA_SOURCE.get(run_id),
            'task_visible': 'task_turns.jsonl' in files,
            'aux_visible': 'cycles.jsonl' in files,
            'memory_visible': 'cycles.jsonl' in files,
            'evaluation_visible': 'evaluation.jsonl' in files or 'INDEX.json' in files,
            'reminder_linked': 'reminders.jsonl' in files,
            'package_kind': 'single_visible_projection',
        }
    ga_history = REPO / 'experiment_runner/ga_only_historical_visible_20261025'
    if ga_history.is_dir():
        checked.append(str(ga_history.relative_to(REPO)).replace('\\', '/'))
        for directory in ga_history.iterdir():
            index = directory / 'INDEX.json'
            if not index.is_file():
                continue
            data = json.loads(index.read_bytes())
            run_id = data['run_id']
            if run_id != directory.name or run_id in found:
                raise ValueError('GA public run identity duplicated or mismatched')
            found[run_id] = {
                'path': str(directory.relative_to(REPO)).replace('\\', '/'),
                'source_sha': None, 'task_visible': (directory / 'task_turns.jsonl').is_file(),
                'aux_visible': False, 'memory_visible': False,
                'evaluation_visible': (directory / 'evaluation.jsonl').is_file(),
                'reminder_linked': False,
                'package_kind': 'ga_historical_visible_projection',
            }
    for generic_name in ('historical_visible_sources_20261025',
                         'evidence_gap_two_real_visible_20261025'):
        generic = REPO / 'experiment_runner' / generic_name
        if not generic.is_dir():
            continue
        checked.append(str(generic.relative_to(REPO)).replace('\\', '/'))
        for directory in generic.iterdir():
            index = directory / 'INDEX.json'
            if not index.is_file():
                continue
            data = json.loads(index.read_bytes())
            run_id = data['run_id']
            if run_id != directory.name or run_id in found:
                raise ValueError('generic public run identity duplicated or mismatched')
            items = {item['public'] for item in data['files']}
            derived = data.get('derived_reminder_links') or {}
            statuses = derived.get('statuses') or {}
            found[run_id] = {
                'path': str(directory.relative_to(REPO)).replace('\\', '/'),
                'source_sha': None, 'task_visible': 'task_events.jsonl.gz' in items,
                'aux_visible': any(name.startswith(('pma_', 'pos_')) for name in items),
                'memory_visible': any(name.startswith('pma_memory') for name in items),
                'evaluation_visible': 'live_result.json.gz' in items,
                'reminder_linked': bool(derived),
                'reminder_unmatched': sum(count for status, count in statuses.items()
                    if status != 'exact_text_in_complete_task_request_with_visible_response'),
                'package_kind': 'generic_source_projection',
            }
    return found, checked


def _events(run: Path) -> tuple[bool, int, int]:
    paths = list((run / 'jobs').glob('*/*/agent/research_events.jsonl'))
    if len(paths) != 1:
        return False, 0, 0
    attempts = 0
    visible = 0
    with paths[0].open('rb') as stream:
        for raw in stream:
            if b'provider_request_attempt' in raw or b'provider_response_content' in raw:
                try:
                    kind = json.loads(raw).get('event_type')
                    attempts += kind == 'provider_request_attempt'
                    visible += kind == 'provider_response_content'
                except (ValueError, TypeError):
                    pass
    return True, attempts, visible


def _archive_commit(public_path: str | None) -> str | None:
    if not public_path:
        return None
    result = subprocess.run(
        ['git', 'log', '-1', '--format=%H', '--', public_path],
        cwd=REPO, capture_output=True, text=True, check=True)
    return result.stdout.strip() or None


def build(longcontext: Path, drive: Path) -> dict:
    public, checked = _public_packages()
    entries = {}
    probes = []
    roots_examined = []
    for parent, label in ((longcontext, 'LongContext'), (drive, 'drive')):
        for root in parent.iterdir():
            if (not root.is_dir() or root.name in EXCLUDED or
                    not root.name.startswith(PREFIXES[label])):
                continue
            roots_examined.append({'area': label, 'directory_name': root.name})
            for live_path in root.rglob('live_result.json'):
                if live_path.parent.name != 'archive':
                    continue
                try:
                    live = json.loads(live_path.read_bytes())
                except (OSError, ValueError):
                    continue
                if live.get('zero_model_fixture_only') is not False:
                    continue
                run_id = live.get('run_id')
                if not isinstance(run_id, str):
                    continue
                failure = live.get('primary_failure') or {}
                if isinstance(failure, dict) and 'test-only pre-Harbor' in str(failure.get('message', '')):
                    probes.append({'run_id': run_id, 'batch': root.name,
                                   'classification': 'real_auxiliary_diagnostic_not_Task_episode'})
                    continue
                run = live_path.parent.parent
                if run_id in entries:
                    raise ValueError(f'duplicate real run identity: {run_id}')
                has_events, task_attempts, task_visible_responses = _events(run)
                host = run / 'host_private/archive'
                initialization_only = False
                host_events = host / 'events.jsonl'
                terminal_record = live.get('stateful_task_terminal') or {}
                if (not has_events and live.get('research_candidate') == 'pma_stateful_memory_v1'
                        and terminal_record.get('result') == 'EXCEPTION' and host_events.is_file()):
                    kinds = [json.loads(raw).get('kind') for raw in host_events.read_bytes().splitlines()]
                    initialization_only = bool(kinds) and set(kinds) == {'initialize'}
                task_started = (False if initialization_only else
                                task_visible_responses > 0 if has_events else None)
                aux_original = any((host / filename).exists() for filename in
                                   ('memory_payload.jsonl', 'gap_visible_transport.jsonl',
                                    'role_transport.jsonl', 'events.jsonl')) or any(
                        (run / 'control/pos_archive' / filename).exists() for filename in
                        ('events.provider.jsonl', 'events.jsonl'))
                memory_original = any((host / filename).exists() for filename in
                                      ('memory.json', 'gap_cycle.jsonl', 'accepted.jsonl'))
                candidate = live.get('research_candidate')
                condition = live.get('condition')
                ga_only = condition == 'A'
                package = public.get(run_id, {})
                spec_path = run / 'control/harbor_spec.json'
                spec = json.loads(spec_path.read_bytes()) if spec_path.is_file() else {}
                authorization_path = run.parent.parent / 'authorization.json'
                authorization = (json.loads(authorization_path.read_bytes())
                                 if authorization_path.is_file() else {})
                manifest_path = run.parent.parent / 'manifest.json'
                manifest = json.loads(manifest_path.read_bytes()) if manifest_path.is_file() else {}
                frozen_condition = ((manifest.get('config') or {}).get('conditions') or {}).get(condition)
                native = live.get('native_result') or {}
                reward = (native.get('rewards') or {}).get('reward')
                if reward is None:
                    reward = 'unavailable'
                coverage = {
                    'task_request_response_actions_receipts':
                        'A' if package.get('task_visible') else
                        'E' if initialization_only else 'F' if not has_events else
                        'B' if task_attempts else 'E',
                    'auxiliary_phase_requests_responses':
                        'E' if ga_only else 'A' if package.get('aux_visible') else
                        'B' if aux_original else 'F',
                    'memory_gap_changes':
                        'E' if ga_only else 'A' if package.get('memory_visible') else
                        'B' if memory_original else 'F',
                    'reminder_delivery_and_followup':
                        'E' if ga_only else 'A' if package.get('reminder_linked') else
                        'F',
                    'native_evaluation_public_result':
                        'A' if package.get('evaluation_visible') else
                        'B' if native.get('status') else 'F',
                }
                missing = []
                if coverage['task_request_response_actions_receipts'] == 'E':
                    missing.append('Only failed initialization was recorded before Task, or no Task HTTP attempt exists in the retained event stream; no Task behavior can be inferred.')
                elif coverage['task_request_response_actions_receipts'] == 'F':
                    missing.append('Task event original was not found in the selected run directory; Task visibility is unverified.')
                elif task_attempts and not task_started:
                    missing.append('Generation was attempted but no complete Task-visible response was recorded; do not infer model silence or tool behavior.')
                if not package:
                    missing.append('No verified per-run redacted visible-content package located in searched public paths.')
                if package.get('reminder_unmatched'):
                    missing.append(f"{package['reminder_unmatched']} recorded reminder(s) lack exact text in a later complete Task request with visible response; do not count them as delivered.")
                if package.get('package_kind') == 'generic_source_projection' and not package.get('reminder_linked') and not ga_only:
                    missing.append('Auxiliary and Task streams are public, but reminder-to-request linkage has not been independently established for this variant.')
                if candidate is None and condition == 'B' and not frozen_condition:
                    missing.append('Candidate identity absent from this live_result; consult frozen manifest before assigning a specific PMA variant.')
                entries[run_id] = {
                    'run_id': run_id, 'task': live.get('task'), 'condition': condition,
                    'research_candidate': candidate,
                    'method': 'ga-only' if ga_only else candidate or frozen_condition,
                    'execution_source_sha': (package.get('source_sha') or
                        spec.get('audited_code_commit') or
                        authorization.get('audited_code_commit') or GA_SOURCE.get(run_id)),
                    'archive_commit': _archive_commit(package.get('path')),
                    'batch': root.name,
                    'task_started': task_started, 'task_http_attempts_observed': task_attempts,
                    'task_visible_responses_observed': task_visible_responses,
                    'terminal': ('recorded_failure_details_private' if failure else
                                 'completed_or_scored' if native.get('status') == 'native_recorded'
                                 else 'unavailable'),
                    'evaluation_status': native.get('status') or 'unavailable',
                    'reward': reward, 'coverage': coverage,
                    'private_originals_present': {'task_events': has_events,
                        'auxiliary': aux_original, 'memory': memory_original,
                        'live_result': True},
                    'public_path': package.get('path'),
                    'known_gaps_and_impact': missing,
                }
    legacy = (
        ('six_task_live_batch_20261014_r1/raw/arms',
         '1272f883aea9e8ffb61fa78f7c610537f2b10f64', 'hash_only'),
        ('live_batch_retry_20261014/raw/arms',
         'e8a351cbb2006f056ab7faac1754280cc02396e1', 'hash_only'),
        ('two_task_live_20261015/REAL_BATCH_ARCHIVE_V3/raw/arms',
         'bfbb4103f4d694ecd4cb0afc62e38a27a5974743', 'complete'),
    )
    legacy_checked = []
    for relative, source_sha, task_capture in legacy:
        base = D / relative
        if not base.is_dir():
            continue
        legacy_checked.append(str(base.relative_to(REPO)).replace('\\', '/'))
        for arm in base.iterdir():
            live_path = arm / 'archive/live_result.json'
            if not live_path.is_file():
                continue
            live = json.loads(live_path.read_bytes())
            run_id = live.get('run_id')
            if not run_id or run_id in entries or live.get('zero_model_fixture_only') is True:
                continue
            if live.get('condition') not in ('A', 'B'):
                continue
            task_events = list((arm / 'jobs').glob('*/*/agent/research_events.jsonl'))
            attempts = 0
            visible_responses = 0
            if len(task_events) == 1:
                with task_events[0].open('rb') as stream:
                    for raw in stream:
                        try:
                            kind = json.loads(raw).get('event_type')
                            attempts += kind == 'provider_request_attempt'
                            visible_responses += kind == 'provider_response_content'
                        except (ValueError, TypeError):
                            pass
            host = arm / 'host_private/archive'
            aux = (host / 'memory_payload.jsonl').is_file()
            ga_only = live['condition'] == 'A'
            native = live.get('native_result') or {}
            reward = (native.get('rewards') or {}).get('reward')
            if reward is None:
                reward = 'unavailable'
            public_path = str(arm.relative_to(REPO)).replace('\\', '/')
            complete = (task_capture == 'complete' and len(task_events) == 1 and
                        attempts == visible_responses and attempts > 0)
            gaps = [
                'Original external private batch root is not present on this machine; the existing redacted archive and source-hash index remain, but original hashes cannot be rechecked locally.'
            ]
            if not complete:
                gaps.append('Contemporaneous provider_request_ready was hash_only and parsed visible response was not captured. Console/tool logs and hashes cannot reconstruct full model-visible Task text; direct prompt/response causal audit is impossible.')
            entries[run_id] = {
                'run_id': run_id, 'task': live.get('task'),
                'condition': live['condition'], 'research_candidate': None,
                'method': 'ga-only' if ga_only else 'GA_plus_fixed_upstream_PMA',
                'execution_source_sha': source_sha,
                'archive_commit': _archive_commit(public_path),
                'batch': relative.split('/')[0],
                'task_started': attempts > 0, 'task_http_attempts_observed': attempts,
                'task_visible_responses_observed': visible_responses,
                'terminal': ('recorded_failure_details_private' if live.get('primary_failure')
                             else 'completed_or_scored' if native.get('status') == 'native_recorded'
                             else 'unavailable'),
                'evaluation_status': native.get('status') or 'unavailable',
                'reward': reward,
                'coverage': {
                    'task_request_response_actions_receipts': 'A' if complete else 'C',
                    'auxiliary_phase_requests_responses': 'E' if ga_only else 'A' if aux else 'F',
                    'memory_gap_changes': 'E' if ga_only else 'A' if aux else 'F',
                    'reminder_delivery_and_followup': 'E' if ga_only else
                        'A' if complete and aux else 'C' if aux else 'F',
                    'native_evaluation_public_result': 'A',
                },
                'private_originals_present': {'task_events': False,
                    'auxiliary': False, 'memory': False, 'live_result': False},
                'public_path': public_path,
                'known_gaps_and_impact': gaps,
            }
    return {
        'schema': 'historical-visible-coverage-v1',
        'status_codes': {'A': 'redacted visible content public and directly auditable',
                         'B': 'private original present, public projection pending',
                         'C': 'not captured or original lost',
                         'D': 'content exists but unsafe to publish; specify masking',
                         'E': 'not applicable or stage not reached',
                         'F': 'not yet established'},
        'search_scope': {'top_level_prefixes': PREFIXES,
                         'excluded_active_root_names': sorted(EXCLUDED),
                         'roots_examined': roots_examined,
                         'public_package_paths_checked': checked,
                         'legacy_redacted_archive_paths_checked': legacy_checked,
                         'not_exhaustive': True},
        'real_runs_found': len(entries),
        'auxiliary_probes_excluded': sorted(probes, key=lambda item: item['run_id']),
        'episodes': [entries[key] for key in sorted(entries)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--longcontext', type=Path, required=True)
    parser.add_argument('--drive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.longcontext, args.drive)
    args.output.write_bytes(canonical(result) + b'\n')
    print(json.dumps({'real_runs_found': result['real_runs_found']}, sort_keys=True))


if __name__ == '__main__':
    main()
