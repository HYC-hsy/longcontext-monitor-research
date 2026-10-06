"""Post-run mechanical blinding; no provider, no gold, no semantic scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage1_plan import CASES, REPLICATES, sha


def load_secret_map(path: Path, commitment: str):
    raw = path.read_bytes()
    if sha(raw) != commitment:
        raise ValueError('Secret blind map commitment mismatch')
    document = json.loads(raw)
    if document.get('schema_version') != 'stage1-secret-blind-map/1':
        raise ValueError('Unknown secret blind map schema')
    entries = document.get('pairs')
    if not isinstance(entries, list) or len(entries) != len(CASES) * len(REPLICATES):
        raise ValueError('Secret blind map pair count mismatch')
    mapping = {}
    for entry in entries:
        key = (entry.get('case_id'), entry.get('replicate'))
        first = entry.get('A')
        if key in mapping or key[0] not in CASES or key[1] not in REPLICATES:
            raise ValueError('Secret blind map has missing/duplicate/unknown pair')
        if first not in ('current', 'constitution'):
            raise ValueError('Secret blind map has invalid condition')
        mapping[key] = {'A': first, 'B': 'constitution' if first == 'current' else 'current'}
    if set(mapping) != {(case, rep) for case in CASES for rep in REPLICATES}:
        raise ValueError('Secret blind map does not cover all pairs')
    return mapping


def natural_output(record):
    return '\n'.join(block.get('text', '') for block in record.get('raw_response_blocks') or []
                     if block.get('type') == 'text')


def export(records, destination: Path, secret_map_path: Path, commitment: str):
    secret_map = load_secret_map(secret_map_path, commitment)
    by_key = {}
    for record in records:
        key = (record['case_id'], record['replicate'], record['condition'])
        if key in by_key:
            raise ValueError('Duplicate logical decision in blind export')
        by_key[key] = record
    blind, mapping = [], []
    for case_id in CASES:
        for replicate in REPLICATES:
            first = secret_map[(case_id, replicate)]['A']
            second = secret_map[(case_id, replicate)]['B']
            pair = []
            for label, condition in (('A', first), ('B', second)):
                record = by_key.get((case_id, replicate, condition))
                if record is None or record.get('status') != 'response_recorded':
                    raise ValueError('Cannot blind an absent or failed scientific response')
                pair.append({'label': f'Response {label}',
                             'selected_action': record['selected_action'],
                             'intervention_message': record.get('intervention_message'),
                             'natural_language_output': natural_output(record)})
                mapping.append({'case_id': case_id, 'replicate': replicate,
                                'response_label': label, 'condition': condition,
                                'trial_id': record['trial_id']})
            blind.append({'case_id': case_id, 'replicate': replicate,
                          'frame': by_key[(case_id, replicate, first)]['frame'],
                          'responses': pair})
    if len(by_key) != 54:
        raise ValueError('Blind export requires exactly the planned 54 decisions')
    blind_path = destination / 'blind' / 'blind_review.json'
    map_path = destination / 'sealed_condition_map' / 'map.json'
    for path, value in ((blind_path, {'pairs': blind}), (map_path, {'mapping': mapping})):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8') + b'\n')
    return blind_path, map_path


def load_records(root: Path):
    return [json.loads(path.read_bytes()) for path in sorted(root.glob('??_*/record.json'))]


def main():
    parser = argparse.ArgumentParser(description='Offline post-run condition-blind export')
    parser.add_argument('--records-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--secret-blind-map', type=Path, required=True)
    args = parser.parse_args()
    from stage1_runner import validate_plan
    plan = validate_plan()
    export(load_records(args.records_root), args.output, args.secret_blind_map,
           plan['blind_map_commitment_sha256'])


if __name__ == '__main__':
    main()
