"""Separate post-run exact-action scoring; this is the only Stage 1 gold reader."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage1_blind_export import load_records


PANEL = Path(__file__).resolve().parent


def score(records, gold_path=PANEL / 'sealed' / 'gold.json'):
    gold = json.loads(gold_path.read_bytes())['cases']
    return [{'case_id': record['case_id'], 'replicate': record['replicate'],
             'condition': record['condition'], 'trial_id': record['trial_id'],
             'selected_action': record.get('selected_action'),
             'expected_action': gold[record['case_id']]['expected_control_class'],
             'exact_action_match': record.get('selected_action') ==
                                   gold[record['case_id']]['expected_control_class']}
            for record in records if record.get('status') == 'response_recorded']


def main():
    parser = argparse.ArgumentParser(description='Offline scoring after response archival')
    parser.add_argument('--records-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = score(load_records(args.records_root))
    args.output.write_bytes(json.dumps(rows, ensure_ascii=False, indent=2).encode('utf-8') + b'\n')


if __name__ == '__main__':
    main()
