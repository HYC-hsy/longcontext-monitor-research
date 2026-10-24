"""Export existing visible event/auxiliary sources without replaying a run.

This intentionally makes no claim that a source contains an unrecorded response.
It does not open verifier scripts, hidden tests, profiles, or authorizations.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import private_values
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_batch20_visible import _one_json, _stream
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_gap_visible_audit import (
    BEARER, KEY, THINKING_TAG, URL, Sanitizer, canonical, file_sha,
)


HOST_STREAMS = ('accepted.jsonl', 'events.jsonl', 'gap_cycle.jsonl',
                'gap_visible_transport.jsonl', 'memory_payload.jsonl',
                'memory_transport.jsonl', 'role_calls.jsonl',
                'provider_events.jsonl', 'native_count.jsonl', 'failures.jsonl')
HOST_OBJECTS = ('memory.json', 'trajectory_memory.json')
POS_STREAMS = ('events.jsonl', 'events.provider.jsonl')


def export(run_root: Path, output: Path, run_id: str, secrets: list[str]) -> dict:
    root = run_root.resolve(strict=True)
    live_path = root / 'archive/live_result.json'
    live = json.loads(live_path.read_bytes())
    if live.get('run_id') != run_id or live.get('zero_model_fixture_only') is not False:
        raise ValueError('not the selected completed real run')
    if output.exists():
        raise FileExistsError(output)
    selected: list[tuple[Path, str, bool]] = []
    events = list((root / 'jobs').glob('*/*/agent/research_events.jsonl'))
    if len(events) > 1:
        raise ValueError('ambiguous Task event sources')
    if events:
        selected.append((events[0], 'task_events.jsonl.gz', True))
    terminal = list((root / 'jobs').glob('*/*/agent/task_terminal.json'))
    if len(terminal) > 1:
        raise ValueError('ambiguous Task terminal sources')
    if terminal:
        selected.append((terminal[0], 'task_terminal.json.gz', False))
    for source_dir, prefix, stream_names, object_names in (
            (root / 'host_private/archive', 'pma_', HOST_STREAMS, HOST_OBJECTS),
            (root / 'control/pos_archive', 'pos_', POS_STREAMS, ())):
        if not source_dir.is_dir():
            continue
        for name in stream_names:
            path = source_dir / name
            if path.is_file():
                selected.append((path, prefix + name + '.gz', True))
        for name in object_names:
            path = source_dir / name
            if path.is_file():
                selected.append((path, prefix + name + '.gz', False))
    selected.append((live_path, 'live_result.json.gz', False))
    if not selected:
        raise ValueError('no selected source')
    output.mkdir(parents=True)
    sanitizer = Sanitizer(secrets)
    files = []
    for source, name, is_stream in selected:
        target = output / name
        item = (_stream(source, target, root, sanitizer) if is_stream else
                _one_json(source, target, root, sanitizer))
        files.append(item)
    for item in files:
        with gzip.open(output / item['public'], 'rt', encoding='utf-8') as stream:
            shown = stream.read()
        if (BEARER.search(shown) or KEY.search(shown) or URL.search(shown) or
                THINKING_TAG.search(shown) or any(secret in shown for secret in secrets)):
            raise ValueError(f'sensitive marker remains: {item["public"]}')
    package = {
        'schema': 'historical-visible-sources-v1', 'run_id': run_id,
        'identity': {'task': live.get('task'), 'condition': live.get('condition'),
                     'research_candidate': live.get('research_candidate'),
                     'zero_model_fixture_only': False},
        'evaluation': {'status': (live.get('native_result') or {}).get('status'),
                       'reward': ((live.get('native_result') or {}).get('rewards') or {}).get('reward'),
                       'test_script_or_hidden_assertions_exported': False},
        'public_kind': 'redacted_reencoded_gzip_jsonl_not_original_http_bytes',
        'files': files,
        'excluded': ['credentials', 'private_profiles', 'private_endpoints',
                     'hidden_reasoning', 'hidden_tests', 'raw_http_headers',
                     'verifier_script', 'hidden_test_stdout'],
        'limits': ['The selected sources can contain truncated Task-visible tool output; no lost bytes are reconstructed.',
                   'Source streams are not a new independent transport capture.',
                   'A reminder is not counted as delivered merely because an auxiliary selection produced it.'],
    }
    (output / 'INDEX.json').write_bytes(canonical(package) + b'\n')
    return {'run_id': run_id, 'sources': len(files),
            'task_events': bool(events),
            'auxiliary_sources': sum(item['public'].startswith(('pma_', 'pos_')) for item in files)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.run_root, args.output, args.run_id,
                            private_values(args.task_profile, args.pma_profile)), sort_keys=True))


if __name__ == '__main__':
    main()
