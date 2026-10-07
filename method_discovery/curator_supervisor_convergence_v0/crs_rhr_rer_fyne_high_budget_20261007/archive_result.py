"""Archive the sole completed trial and index host-turn usage mechanically."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_rhr_rer_fyne_gate_replacement_20261007 import archive_result as previous


ROOT = Path(__file__).resolve().parent
RUN_ID = 'crs-rhr-rer-v0-fyne-bji-high-budget-r1'
CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate')
DESTINATION = ROOT / 'archive' / 'r1'
PRIVATE = Path(r'E:\crs_rhr_rer_fyne_high_budget_private_20261007')


def rows(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def turn_accounting():
    audit = DESTINATION / 'monitor/audit'
    dialogue = rows(audit / 'dialogue.jsonl')
    reviews = rows(audit / 'reviews.jsonl')
    review_ids = [row['review_id'] for row in dialogue if row.get('event') == 'review_context']
    if len(review_ids) != len(reviews) or len(set(review_ids)) != len(review_ids):
        raise RuntimeError('Review identity/order cannot be mechanically reconciled')
    inputs = Counter(row['review_id'] for row in dialogue if row.get('event') == 'model_input')
    outputs = Counter(row['review_id'] for row in dialogue if row.get('event') == 'model_output')
    if inputs != outputs:
        raise RuntimeError('Supervisor request/response counts differ')
    situation = {}
    for row in dialogue:
        if row.get('event') == 'supervisory_situation_surface':
            situation.setdefault(row['review_id'], row.get('shown_through_cursor'))
    frames = []
    root_groups = defaultdict(list)
    for index, (review_id, review) in enumerate(zip(review_ids, reviews), 1):
        handoff = review.get('handoff')
        frame = {
            'review_ordinal': index, 'review_id': review_id,
            'frame': review['frame'], 'task_cursor_at_first_situation': situation.get(review_id),
            'supervisor_model_turns': inputs[review_id],
            'terminal_action': review['action']['kind'], 'root_handoff': handoff,
        }
        frames.append(frame)
        if handoff is not None:
            key = (handoff['request_id'], handoff['generation'], handoff['cursor'])
            root_groups[key].append(frame)
    root_handoffs = []
    for key, members in root_groups.items():
        cumulative = 0
        subreviews = []
        for index, member in enumerate(members):
            prior = cumulative
            cumulative += member['supervisor_model_turns']
            subreviews.append({
                'review_id': member['review_id'], 'review_ordinal': member['review_ordinal'],
                'phase': 'initial_root' if index == 0 else 'post_internal_root_reestimate',
                'model_turns': member['supervisor_model_turns'],
                'cumulative_turns_before': prior, 'cumulative_turns_after': cumulative,
                'terminal_action': member['terminal_action'],
            })
        root_handoffs.append({
            'handoff': {'request_id': key[0], 'generation': key[1], 'cursor': key[2]},
            'initial_root_turns': subreviews[0]['model_turns'],
            'subreviews': subreviews, 'cumulative_root_turns': cumulative,
            'crossed_20_turns': cumulative > 20,
            'terminal_disposition': subreviews[-1]['terminal_action'],
            'host_cumulative_ceiling': 300,
        })
    ordinary = [frame for frame in frames if frame['frame'] != 'root']
    crossed = [frame for frame in ordinary if frame['supervisor_model_turns'] > 20]
    rer = [row for row in dialogue if str(row.get('event', '')).startswith('rer_')]
    result = {
        'schema': 'supervisor-high-budget-turn-accounting/1',
        'run_id': RUN_ID, 'unit': 'model_input/model_output pair',
        'ordinary_review_host_ceiling': 300, 'root_handoff_cumulative_host_ceiling': 300,
        'supervisor_model_requests': sum(inputs.values()),
        'supervisor_model_responses': sum(outputs.values()),
        'review_count': len(frames), 'reviews': frames,
        'ordinary_review_count': len(ordinary),
        'max_ordinary_review_turns': max((f['supervisor_model_turns'] for f in ordinary), default=0),
        'ordinary_reviews_over_20': len(crossed),
        'first_ordinary_over_20': crossed[0] if crossed else None,
        'root_handoffs': root_handoffs,
        'rer_events': [
            {key: row.get(key) for key in ('event', 'review_id', 'handoff', 'frame_sequence',
                                          'root_horizon_digest', 'model_turn')}
            for row in rer],
    }
    raw.write(DESTINATION / 'TURN_ACCOUNTING.json', result)
    summary_path = DESTINATION / 'MECHANICAL_SUMMARY.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    summary['root_frame_input_count'] = sum(row.get('event') == 'root_frame_input' for row in dialogue)
    summary['root_handoff_count'] = len(root_handoffs)
    summary['high_budget_turn_accounting'] = {
        key: result[key] for key in (
            'supervisor_model_requests', 'review_count', 'ordinary_review_count',
            'max_ordinary_review_turns', 'ordinary_reviews_over_20', 'first_ordinary_over_20',
            'root_handoffs')}
    summary['high_budget_turn_accounting']['index_sha256'] = raw.digest(DESTINATION / 'TURN_ACCOUNTING.json')
    raw.write(summary_path, summary)


def file_manifest():
    files = []
    for path in sorted(DESTINATION.rglob('*')):
        if path.is_file() and path.name != 'ALL_ARCHIVED_FILES_SHA256.json':
            files.append({'path': path.relative_to(DESTINATION).as_posix(),
                          'bytes': path.stat().st_size, 'sha256': raw.digest(path)})
    raw.write(DESTINATION / 'ALL_ARCHIVED_FILES_SHA256.json', {
        'schema': 'raw-archive-file-identities/1', 'run_id': RUN_ID, 'files': files,
    })


def main():
    manifest = json.loads((CAMPAIGN / 'runs' / RUN_ID / 'manifest.json').read_text(encoding='utf-8'))
    if (manifest.get('valid') is not True or manifest.get('trial_outcome') != 'agent_phase_completed'):
        raise RuntimeError('Legal agent-phase termination required for completed archive')
    if DESTINATION.exists():
        raise RuntimeError('Archive already exists; refusing overwrite')
    previous.ROOT = ROOT
    previous.RUN_ID = RUN_ID
    previous.CAMPAIGN = CAMPAIGN
    previous.DESTINATION = DESTINATION
    previous.inherited.RUN_ID = RUN_ID
    previous.inherited.ROOT = ROOT
    previous.inherited.CAMPAIGN = CAMPAIGN
    previous.inherited.DESTINATION = DESTINATION
    previous.inherited.STAGING = PRIVATE / 'archive_stage'
    previous.inherited.EXTRACTION = PRIVATE / 'final_workspace_extract'
    previous.inherited.main()
    previous.build_index()
    turn_accounting()
    file_manifest()
    print(json.dumps({'archive': str(DESTINATION),
                      'turn_accounting_sha256': raw.digest(DESTINATION / 'TURN_ACCOUNTING.json'),
                      'file_manifest_sha256': raw.digest(DESTINATION / 'ALL_ARCHIVED_FILES_SHA256.json')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
