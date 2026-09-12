"""Offline descriptive audit of a completed native trial; no model or Docker calls."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def audit(root):
    root = Path(root)
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    memory = read(root / 'trajectory_memory.json')
    result = read(root / 'native_result.json')
    calls = [json.loads(line) for line in (root / 'model_calls.jsonl').read_text(encoding='utf-8').splitlines()]
    episodes = sorted((root / 'agent').glob('episode-*/response.txt'),
                      key=lambda p: int(p.parent.name.split('-')[-1]))
    usage = {}
    for actor in ('task', 'memory'):
        rows = [row for row in calls if row['actor'] == actor]
        usage[actor] = {'logical_calls': len(rows),
            'elapsed_seconds': sum(row['elapsed_seconds'] for row in rows),
            'failed_calls': sum(row['status'] != 'returned' for row in rows),
            'missing_usage_calls': sum(row.get('usage') is None for row in rows),
            **{key: sum((row.get('usage') or {}).get(key, 0) or 0 for row in rows)
               for key in ('prompt_tokens', 'completion_tokens', 'cache_tokens', 'cost_usd')}}
    receipts = []
    for step in memory['steps']:
        if not step['should_inject']:
            continue
        episode = step['trigger_step']
        debug = read(root / f'agent/episode-{episode}/debug.json')
        receipts.append({'memory_step': step['step_id'], 'task_episode_zero_based': episode,
            'exact_text_in_current_user_message': any(step['context_for_action'] in text
                for text in strings(debug['messages'][-1]))})
    commands = []
    for path in episodes:
        for command in re.findall(r'<keystrokes[^>]*>(.*?)</keystrokes>',
                                  path.read_text(encoding='utf-8'), flags=re.S):
            if re.search(r'\bgo(?:fmt)?\s+(?:test|build|vet|fmt)\b|\bgofmt\b', command):
                commands.append({'episode': path.parent.name, 'command': command.strip()})
    material = ('native_result.json', 'trajectory_memory.json', 'memory.json',
                'model_calls.jsonl', 'agent/trajectory.json', 'agent/recording.cast',
                'verifier/test-stdout.txt')
    return {'status': result['status'], 'reward': result['reward'],
        'evaluation_status': result['evaluation_status'], 'usage': usage,
        'memory_summary': memory['summary'], 'reminder_delivery': receipts,
        'verification_commands_in_explicit_task_responses': commands,
        'task_episodes': len(episodes),
        'summarization_count': result['task_usage']['metadata']['summarization_count'],
        'memory_operation_errors': sum(not op.get('success', True)
            for step in memory['steps'] for op in step.get('operations', [])),
        'material_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                            for name in material},
        'limits': ['descriptive, not causal', 'cost_usd is client estimate, not relay bill',
                   'internal retry usage may be missing', 'command scan is not general shell analysis']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    report = audit(args.trial)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'episodes': report['task_episodes'],
        'reminders': len(report['reminder_delivery']),
        'all_delivered': all(r['exact_text_in_current_user_message'] for r in report['reminder_delivery']),
        'verification_commands': report['verification_commands_in_explicit_task_responses']}))
