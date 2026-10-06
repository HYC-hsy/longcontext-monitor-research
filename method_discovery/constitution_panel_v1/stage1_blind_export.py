"""Post-run mechanical blinding; no provider, no gold, no semantic scoring."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage1_plan import CASES, REPLICATES


def natural_output(record):
    return '\n'.join(block.get('text', '') for block in record.get('raw_response_blocks') or []
                     if block.get('type') == 'text')


def export(records, destination: Path):
    by_key = {}
    for record in records:
        key = (record['case_id'], record['replicate'], record['condition'])
        if key in by_key:
            raise ValueError('Duplicate logical decision in blind export')
        by_key[key] = record
    blind, mapping = [], []
    for case_index, case_id in enumerate(CASES):
        for replicate_index, replicate in enumerate(REPLICATES):
            first = 'current' if (case_index + replicate_index) % 2 == 0 else 'constitution'
            second = 'constitution' if first == 'current' else 'current'
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
    args = parser.parse_args()
    export(load_records(args.records_root), args.output)


if __name__ == '__main__':
    main()
