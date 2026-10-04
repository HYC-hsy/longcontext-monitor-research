"""Deterministic, zero-model RSH projection of archived DCM dialogue facts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from monitor_agent_core.rsh_v0 import ReleaseSupportHorizon


RECORDS = {
    'fyne': '02_caea820b492d9a880dddf13a0649f2fd',
    'kitex': '03_20c3ea3c5675f07f201f6b1d48762011',
}


class ArchivedWorkspace:
    def __init__(self, record_root):
        self.record_root = record_root

    def resolve_read(self, locator):
        relative = Path(locator)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] != 'monitor':
            raise ValueError('archive locator outside monitor')
        return self.record_root / relative


def replay_record(record_root):
    dialogue = record_root / 'monitor/audit/dialogue.jsonl'
    emissions = []
    collector = ReleaseSupportHorizon(ArchivedWorkspace(record_root), lambda *a, **k: None)
    for number, line in enumerate(dialogue.read_text(encoding='utf-8').splitlines(), 1):
        row = json.loads(line)
        if row.get('event') == 'root_frame_input':
            if collector.active:
                collector.end()
            collector.begin(row['review_id'], row['handoff'])
        collector.observe(row, number)
        if (row.get('event') == 'dcm_boundary_issued' and row.get('frame') == 'root'
                and row.get('release_kind') == 'allow_complete'):
            if not collector.active or collector.review_id != row['review_id']:
                raise ValueError('root boundary has no matching active root frame')
            content = collector.render(row['challenge_id'])
            emissions.append({
                'boundary_locator': f'monitor/audit/dialogue.jsonl#{number}',
                'review_id': row['review_id'], 'challenge_id': row['challenge_id'],
                'horizon': collector.snapshot(), 'rendered_horizon': content,
                'rendered_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            })
    return {'dialogue': str(dialogue),
            'dialogue_sha256': hashlib.sha256(dialogue.read_bytes()).hexdigest(),
            'root_boundaries': emissions}


def main():
    repo = Path(__file__).resolve().parents[2]
    source = repo / 'method_discovery/runs/dcm_v0_20261005/records'
    result = {name: replay_record(source / folder) for name, folder in RECORDS.items()}
    if len(result['fyne']['root_boundaries']) != 3 or len(result['kitex']['root_boundaries']) != 1:
        raise ValueError('unexpected historical root boundary count')
    destination = repo / 'method_discovery/runs/rsh_v0_20261005'
    destination.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    (destination / 'RSH_REPLAY.json').write_text(raw, encoding='utf-8')
    summary = {
        'source': 'archived DCM-v0 dialogue and CFS manifests; no provider calls',
        'replay_sha256': hashlib.sha256(raw.encode('utf-8')).hexdigest(),
        'records': {
            name: [{
                'boundary_locator': row['boundary_locator'],
                'root_identity': row['horizon']['root_identity'],
                'fresh_task_file_reads': len(row['horizon']['fresh_task_file_reads']),
                'fresh_supervisor_code_runs': len(row['horizon']['fresh_supervisor_code_runs']),
                'cfs_manifest_locator': (row['horizon']['latest_full_cfs_situation'] or {}).get(
                    'manifest_locator'),
                'rendered_sha256': row['rendered_sha256'],
            } for row in entry['root_boundaries']]
            for name, entry in result.items()
        },
    }
    (destination / 'REPLAY_SUMMARY.json').write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
