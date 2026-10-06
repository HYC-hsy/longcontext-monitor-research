"""Offline mechanical index for the frozen ASE-v1-core discovery records."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from statistics import median

from method_discovery import uc_ase_v1_recovery_freeze as freeze


SELF_AUTHORED = re.compile(r'\b(?:echo|print|printf)\b|\b(?:COMPLETE|VERIFIED|ALL TARGETS)\b', re.I)


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def args(row: dict) -> dict:
    try:
        value = json.loads(row.get('arguments') or '{}')
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError):
        return {}


def index_record(record: Path) -> dict:
    dialogue = read_jsonl(record / 'monitor/audit/dialogue.jsonl')
    public = read_jsonl(record / 'monitor/task_evidence/public_events.jsonl')
    summary = json.loads((record / 'MECHANICAL_SUMMARY.json').read_text(encoding='utf-8'))
    rows = [(i, row) for i, row in enumerate(dialogue, 1)]
    tools = [(i, row, args(row)) for i, row in rows if row.get('event') == 'tool_call']
    inputs = [i for i, row in rows if row.get('event') == 'model_input']
    references = [(i, row) for i, row in rows if row.get('event') == 'ase_reference_initialization_ready']
    starts = [(i, row) for i, row in rows if row.get('event') == 'ase_control_episode_started']
    clears = [(i, row) for i, row in rows if row.get('event') == 'ase_continuity_cleared']
    updates = [(i, row) for i, row in rows if row.get('event') == 'ase_continuity_updated'
               and row.get('source') == 'intervene']
    observations = [(i, row) for i, row in rows
                    if row.get('event') == 'ase_episode_observation_result']
    duplicates = [(i, row) for i, row in rows
                  if row.get('event') == 'ase_exact_duplicate_observation_call']
    cycles = [(i, row) for i, row in rows
              if row.get('event') == 'ase_follow_feedback_cycle_completed']
    attempts = [(i, row) for i, row in rows if row.get('event') == 'ase_release_attempted']
    boundaries = [(i, row) for i, row in rows if row.get('event') == 'ase_reconsideration_boundary']
    root_reviews = {row['review_id'] for _, row in rows if row.get('event') == 'root_frame_input'}
    final_task_turn = max((int(row.get('task_turn') or 0) for row in public), default=0)

    def request_at(line: int) -> int | None:
        found = [ordinal for ordinal, item in enumerate(inputs, 1) if item < line]
        return found[-1] if found else None

    def first_tool(name: str) -> dict | None:
        found = next(((i, row) for i, row, _ in tools if row.get('name') == name), None)
        if found is None:
            return None
        i, row = found
        return {'request_ordinal': request_at(i), 'review_id': row.get('review_id'),
                'model_turn': row.get('turn'), 'dialogue_locator': f'monitor/audit/dialogue.jsonl#{i}'}

    episodes = []
    all_gaps = []
    for position, (start_line, start) in enumerate(starts):
        next_start = starts[position + 1][0] if position + 1 < len(starts) else len(dialogue) + 1
        ending = next(((i, row) for i, row in clears if start_line < i < next_start), None)
        end_line = ending[0] if ending else next_start
        interventions = [(i, row) for i, row in updates if start_line < i < end_line]
        turns = [int(row.get('task_turn') or 0) for _, row in interventions]
        gaps = [right - left for left, right in zip(turns, turns[1:])]
        all_gaps.extend(gaps)
        first_turn = int(start.get('task_turn') or 0)
        end_turn = int(ending[1].get('task_turn') or 0) if ending else final_task_turn
        obs = [row for i, row in observations if start_line < i < end_line]
        patrol = [(i, row) for i, row, a in tools if start_line < i < end_line
                  and row.get('name') == 'wait' and a.get('mode') == 'patrol']
        episode = {
            'start_task_turn': first_turn, 'end_task_turn': end_turn,
            'end_kind': 'executed_patrol' if ending else 'still_active_at_trial_end',
            'task_turn_age': max(0, end_turn - first_turn),
            'intervention_count': len(interventions),
            'interventions': [
                {'task_turn': row.get('task_turn'), 'timestamp': row.get('timestamp'),
                 'review_id': row.get('review_id'), 'action_locator':
                 row.get('anchor', {}).get('action_locator'),
                 'message_sha256': row.get('anchor', {}).get('message_sha256')}
                for _, row in interventions],
            'intervention_task_turn_gaps': gaps,
            'completed_follow_cycles': len([1 for i, _ in cycles if start_line < i < end_line]),
            'file_read_count': sum(row.get('kind') == 'file_read' for row in obs),
            'code_run_count': sum(row.get('kind') == 'code_run' for row in obs),
            'exact_duplicate_count': len([1 for i, _ in duplicates if start_line < i < end_line]),
            'patrol_attempt_count': len(patrol),
            'patrol_reconsideration_count': len([1 for i, row in boundaries
                                                 if start_line < i < end_line
                                                 and row.get('release_kind') == 'wait_patrol']),
            'executed_patrol': ending is not None,
            'root_review_with_episode_active': bool(root_reviews and not ending),
        }
        episodes.append(episode)

    authored = []
    for i, row, a in tools:
        if row.get('name') != 'code_run':
            continue
        command = a.get('script') or a.get('code') or ''
        if isinstance(command, str) and SELF_AUTHORED.search(command):
            authored.append({'dialogue_locator': f'monitor/audit/dialogue.jsonl#{i}',
                             'review_id': row.get('review_id'), 'model_turn': row.get('turn')})
    reference_line = references[0][0] if references else None
    exposure = [row for _, row in rows if row.get('event') == 'ase_context_injected']
    return {
        'run_id': summary['run_id'], 'task': summary['task'], 'condition': summary['condition'],
        'source_summary': 'MECHANICAL_SUMMARY.json',
        'reference': {
            'ready_request': request_at(reference_line) if reference_line else None,
            'ready_review_id': references[0][1].get('review_id') if references else None,
            'first_intervention': first_tool('intervene'), 'first_wait': first_tool('wait'),
            'interventions_before_ready': sum(i < reference_line for i, row, _ in tools
                                              if row.get('name') == 'intervene') if reference_line else None,
            'mutations': sum(row.get('event') == 'ase_reference_mutated' for _, row in rows),
            'exposures': len(exposure),
            'truncated_exposures': sum(bool(row.get('reference_truncated')) for row in exposure),
        },
        'episodes': episodes, 'episode_count': len(episodes),
        'episodes_ending_without_patrol': sum(not row['executed_patrol'] for row in episodes),
        'intervention_cadence': {
            'gaps_task_turns': all_gaps,
            'min': min(all_gaps) if all_gaps else None,
            'median': median(all_gaps) if all_gaps else None,
            'max': max(all_gaps) if all_gaps else None,
            'gaps_le_1': sum(gap <= 1 for gap in all_gaps),
            'gaps_le_2': sum(gap <= 2 for gap in all_gaps),
        },
        'self_authored_command_locators': authored,
        'completion': {
            'root_frame_inputs': sum(row.get('event') == 'root_frame_input' for _, row in rows),
            'root_interventions': sum(row.get('name') == 'intervene' and
                                      row.get('review_id') in root_reviews for _, row, _ in tools),
            'allow_attempts': sum(row.get('name') == 'allow_complete' for _, row, _ in tools),
            'reconsideration_boundaries': len(boundaries),
            'post_boundary_file_reads': sum(row.get('name') == 'file_read' and
                                            any(row.get('review_id') == b.get('review_id')
                                                and i > line for line, b in boundaries)
                                            for i, row, _ in tools),
            'post_boundary_code_runs': sum(row.get('name') == 'code_run' and
                                           any(row.get('review_id') == b.get('review_id')
                                               and i > line for line, b in boundaries)
                                           for i, row, _ in tools),
            'release_confirmed': sum(row.get('event') == 'ase_release_confirmed' for _, row in rows),
        },
        'task_turns_visible': final_task_turn,
        'monitor_reviews': summary['monitor_review_count'],
        'task_requests': summary['task_provider_requests'],
        'monitor_requests': summary['monitor_requests'],
        'native_result': summary['native_result'],
    }


def main() -> None:
    root = freeze.ROOT / 'records'
    for position, (_, run_id) in enumerate(freeze.ORDER, 1):
        record = root / f'{position:02d}_{run_id}'
        target = record / 'ASE_V1_CORE_MECHANICAL_INDEX.json'
        if target.exists():
            raise RuntimeError(f'Index exists: {target}')
        target.write_text(json.dumps(index_record(record), ensure_ascii=False, indent=2) + '\n',
                          encoding='utf-8')
        print(target)


if __name__ == '__main__':
    main()
