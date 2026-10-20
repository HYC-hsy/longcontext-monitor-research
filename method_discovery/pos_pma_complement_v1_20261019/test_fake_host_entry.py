"""Test-only final LiteLLM hop for the real independent PMA host worker."""
import json
import os
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[1] / (
    'curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013')
vendor = root / 'vendor/pma_89e5c0d'
sys.path[:0] = [str(root), str(vendor / 'src'),
                str(vendor / 'external/harbor/src')]

import litellm

capture = Path(os.environ['CANDIDATE_FAKE_HOST_CAPTURE'])
sequence = 0
shared_view = 'pos_pma_shared_view_v1' in sys.argv


async def finite_fake_last_hop(**kwargs):
    global sequence
    sequence += 1
    if sequence > 4 or kwargs.get('model') != 'anthropic/claude-opus-4-8':
        raise RuntimeError('unmatched synthetic PMA network call')
    row = {'sequence': sequence, 'model': kwargs.get('model'),
           'max_tokens': kwargs.get('max_tokens'),
           'temperature': kwargs.get('temperature'),
           'thinking': kwargs.get('thinking'), 'timeout': kwargs.get('timeout'),
           'phase': 'phase1' if kwargs.get('tools') is not None else 'phase2'}
    with capture.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row, sort_keys=True) + '\n')
    content = ('<context_for_action>Synthetic PMA advice.</context_for_action>'
               if sequence == 2 else '<no_intervention/>')
    calls = None
    if shared_view and sequence == 3:
        if '[Recent Trajectory' not in str(kwargs.get('messages')):
            raise AssertionError('synthetic PMA save requires a real prior Task trajectory')
        calls = [{'id': 'synthetic-memory-save', 'type': 'function',
                  'function': {'name': 'memory_save_knowledge',
                               'arguments': json.dumps({'content':
                                   'Synthetic prior Task tool outcome; fallible historical memory.'})}}]
    return {'choices': [{'message': {'content': content, 'tool_calls': calls},
                         'finish_reason': 'stop'}]}


litellm.acompletion = finite_fake_last_hop
worker = root / 'candidate_transport_worker.py'
sys.argv = [str(worker), *sys.argv[1:]]
runpy.run_path(str(worker), run_name='__main__')
