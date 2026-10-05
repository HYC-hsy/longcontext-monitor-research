"""Deterministically replay action-derived CQS over archived Supervisor dialogue.

No provider, task, verifier, or evaluator is constructed here. This is a mechanical
counterfactual rendering of the input surface after already-archived actions.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from monitor_agent_core.cqs_v0 import ControlQuestionState


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'method_discovery/runs/cqs_v0_20261005/CQS_REPLAY.json'
SOURCES = {
    'fyne_dcm': ROOT / 'method_discovery/runs/dcm_v0_20261005/records/'
                         '02_caea820b492d9a880dddf13a0649f2fd/monitor/audit/dialogue.jsonl',
    'kitex_dcm': ROOT / 'method_discovery/runs/dcm_v0_20261005/records/'
                          '03_20c3ea3c5675f07f201f6b1d48762011/monitor/audit/dialogue.jsonl',
}


def replay(path):
    raw = path.read_bytes()
    state = ControlQuestionState(lambda *args, **kwargs: None)
    transitions = []
    review_starts = []
    last_review = None
    last_call_name = None
    last_call_args = {}
    for line_number, line in enumerate(raw.decode('utf-8').splitlines(), 1):
        row = json.loads(line)
        review_id = row.get('review_id')
        if review_id != last_review:
            state.begin_review(review_id)
            last_review = review_id
            last_call_name = None
            last_call_args = {}
            review_starts.append({'review_id': review_id, 'source_line': line_number,
                                  'would_show': state.render()})
        state.observe(row, line_number)
        if row.get('event') == 'tool_call':
            last_call_name = row.get('name')
            try:
                last_call_args = json.loads(row.get('arguments') or '{}')
            except (ValueError, TypeError):
                last_call_args = {}
        if row.get('event') != 'tool_result':
            continue
        data = row.get('data') or {}
        action = row.get('action') or {}
        changed = False
        if last_call_name == 'intervene' and data.get('status') == 'submitted':
            state.submitted_intervention(last_call_args.get('message'))
            changed = True
        elif action.get('kind') == 'wait':
            state.completed_wait(SimpleNamespace(kind='wait', payload=action.get('payload') or {}))
            changed = True
        if changed:
            transitions.append({'review_id': review_id, 'source_line': line_number,
                                'tool': last_call_name, 'action': action or None,
                                'active': state.state is not None,
                                'source': state.state.get('source') if state.state else None,
                                'next_provider_surface': state.render()})
    return {'source': str(path.relative_to(ROOT)).replace('\\', '/'),
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'dialogue_lines': line_number, 'review_count': len(review_starts),
            'review_starts': review_starts, 'action_transitions': transitions}


def main():
    result = {'status': 'deterministic_no_model',
              'surface_rule': 'Only submitted intervene and completed follow/patrol wait update state.',
              'runs': {name: replay(path) for name, path in SOURCES.items()}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(OUT), 'sha256': hashlib.sha256(OUT.read_bytes()).hexdigest(),
                      'summary': {name: {'reviews': data['review_count'],
                                         'transitions': len(data['action_transitions']),
                                         'interventions': sum(t['source'] == 'intervene'
                                                              for t in data['action_transitions']),
                                         'follows': sum(t['source'] == 'wait_follow'
                                                        for t in data['action_transitions']),
                                         'clears': sum(not t['active']
                                                       for t in data['action_transitions'])}
                                  for name, data in result['runs'].items()}}, indent=2))


if __name__ == '__main__':
    main()
