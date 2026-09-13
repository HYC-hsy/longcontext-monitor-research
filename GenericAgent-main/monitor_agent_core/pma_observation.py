"""Map public host events into the author's task + recent-step context."""
from collections import OrderedDict, deque
import json

from .vendor.pma_memory.context import AuthorContext


def preview(value, limit):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + '\n[Clipped; original public source remains available.]'


def records(path):
    if not path.exists():
        return
    with path.open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.endswith('\n'):
                continue
            yield number, json.loads(line)


def observation(workspace, wake):
    # Group pre/post boundaries into real task turns, not eight event records.
    turns = OrderedDict()
    for line, event in records(workspace.evidence_root / 'public_events.jsonl'):
        turn = event.get('task_turn')
        if turn is None:
            raise ValueError('Public event lacks host-normalized task_turn')
        entry = turns.setdefault(turn, {'step': turn, 'analysis': '', 'commands': [], 'observation': ''})
        if event.get('text'):
            entry['analysis'] = preview(event['text'], 10000)
        if event.get('tool_calls'):
            entry['commands'] = [preview(c, 2000) for c in event['tool_calls']]
        if event.get('tool_results') is not None:
            entry['observation'] = preview(event['tool_results'], 10000)
        entry['source'] = f'task/public_events.jsonl#L{line}'
        while len(turns) > 8:
            turns.popitem(last=False)
    author = AuthorContext()
    author._task_description = workspace.resolve_read('task/original_task.txt').read_text(encoding='utf-8')
    author._sliding_window_size = 8
    author._accumulated_observations = [{}] + list(turns.values())
    context = author._get_memory_agent_context()
    context += '\n[Wake metadata, not a verdict]\n' + wake
    context += '\n[Public source locations; latest turn may still be in progress]\n' + '\n'.join(
        entry['source'] for entry in turns.values())
    # Retain selected actual inspection receipts, not the monitor's full repeated
    # conclusions. One serialization layer; already bounded tool results stay so.
    recent = deque(maxlen=4)
    calls = {}
    for line, record in records(workspace.private_root / 'audit/dialogue.jsonl'):
        key = (record.get('review_id'), record.get('tool_id'))
        if record.get('event') == 'tool_call' and record.get('tool_id'):
            calls[key] = {'name': record.get('name'), 'arguments': record.get('arguments'),
                          'source': f'monitor/audit/dialogue.jsonl#L{line}'}
        if record.get('event') == 'tool_result' and record.get('data'):
            data = record['data']
            if 'content' in data or 'stdout' in data:
                call = calls.get(key)
                # Separate bounds keep long command text from erasing the output.
                recent.append('Producing tool call: ' + preview(call or
                    {'source': 'unmatched; do not infer the producing command'}, 3000)
                    + f'\nTool result source: monitor/audit/dialogue.jsonl#L{line}\n'
                    + preview(data, 3000))
    if recent:
        context += '\n[Recent inspection results; not proof of whole-task completion]\n' + '\n'.join(recent)
    receipt = workspace.private_root / 'audit/decision_context_last_input.json'
    if receipt.exists():
        message = json.loads(receipt.read_text(encoding='utf-8')).get('message', '')
        context += '\n[Last submitted correction, not proof of uptake]\n' + preview(message, 4000)
    return context
