"""Read-only, allowlisted public projection of one completed PMA-gap run.

The exporter never reads a verifier script, sends a request, or changes a
private source. Every public row carries private file/line hashes separately
from its own redacted-byte hash in INDEX.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from .archive_live_six_task import private_values


HIDDEN = frozenset({
    'thinking', 'redacted_thinking', 'reasoning_content', 'signature',
    'thinking_signature', 'encrypted_content', 'encrypted_payload',
    'reasoning_phase1', 'reasoning_phase2',
})
PRIVATE = frozenset({
    'metadata', 'provider_url', 'api_key', 'access_token', 'authorization',
    'password', 'credential', 'client_secret', 'private_key', 'api_base',
    'base_url',
})
URL = re.compile(r'https?://[^\s<>"\']+', re.I)
BEARER = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~/+=-]{12,}')
KEY = re.compile(r'\bsk-[A-Za-z0-9_-]{12,}')
PRIVATE_HOST = re.compile(r'(?i)\bhost\.docker\.internal(?::\d+)?\b')
THINKING_TAG = re.compile(r'(?is)<(thinking|redacted_thinking)>.*?</\1>')


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path, root: Path) -> tuple[list[dict], dict]:
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError('private source outside run root')
    result = []
    with path.open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if not raw.strip():
                raise ValueError(f'blank source row: {path.name}:{number}')
            result.append({'value': json.loads(raw), 'source': {
                'file': path.relative_to(root).as_posix(), 'line': number,
                'line_sha256': sha(raw), 'line_bytes': len(raw)}})
    return result, {'file': path.relative_to(root).as_posix(),
                    'bytes': path.stat().st_size, 'sha256': file_sha(path),
                    'rows': len(result)}


class Sanitizer:
    def __init__(self, secrets: list[str]):
        self.secrets = [item for item in secrets if len(item) >= 6]
        self.removals: list[dict] = []

    def clean(self, value: object, where: str = '$') -> object:
        if isinstance(value, dict):
            output = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError('non-string key in selected public data')
                path = f'{where}.{key}'
                if (key == 'thinking' and isinstance(item, dict) and
                        set(item) <= {'type', 'budget_tokens'} and
                        item.get('type') in {'adaptive', 'enabled', 'disabled'}):
                    output[key] = self.clean(item, path)
                    continue
                if key.lower() in HIDDEN | PRIVATE:
                    reason = ('hidden_reasoning' if key.lower() in HIDDEN
                              else 'private_metadata_or_config')
                    self.removals.append({'path': path, 'reason': reason,
                                          'original_value_sha256': sha(canonical(item))})
                    output[key] = {'excluded': reason,
                                   'original_value_sha256': sha(canonical(item))}
                else:
                    output[key] = self.clean(item, path)
            return output
        if isinstance(value, list):
            return [self.clean(item, f'{where}[{n}]') for n, item in enumerate(value)]
        if isinstance(value, str):
            shown = value
            for secret in self.secrets:
                if secret in shown:
                    self.removals.append({'path': where, 'reason': 'private_profile_value',
                                          'occurrences': shown.count(secret)})
                    shown = shown.replace(secret, '[REDACTED_PRIVATE_CONFIG]')
            for pattern, label in ((THINKING_TAG, 'hidden_reasoning_tag'),
                                   (URL, 'url_literal'), (BEARER, 'bearer_token'),
                                   (KEY, 'key_literal'), (PRIVATE_HOST, 'private_host')):
                replacement = '[REDACTED_HIDDEN_THINKING]' if pattern == THINKING_TAG else '[REDACTED]'
                shown, count = pattern.subn(replacement, shown)
                if count:
                    self.removals.append({'path': where, 'reason': label,
                                          'occurrences': count})
            return shown
        if value is None or type(value) in (bool, int, float):
            return value
        raise ValueError(f'unsupported selected value at {where}')


def write_rows(path: Path, values: list[dict], sanitizer: Sanitizer) -> dict:
    hashes = []
    with path.open('xb') as stream:
        for number, value in enumerate(values, 1):
            raw = canonical(sanitizer.clean(value)) + b'\n'
            stream.write(raw)
            hashes.append({'row': number, 'sha256': sha(raw), 'bytes': len(raw)})
    return {'file': path.name, 'sha256': file_sha(path), 'bytes': path.stat().st_size,
            'rows': len(values), 'public_rows': hashes}


def visible_strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from visible_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from visible_strings(child)


def export(run_root: Path, output: Path, secrets: list[str], run_id: str) -> dict:
    run_root = run_root.resolve(strict=True)
    status = json.loads((run_root / 'archive/live_result.json').read_bytes())
    if (status.get('run_id') != run_id or
            status.get('research_candidate') != 'pma_gap_memory_v0' or
            status.get('zero_model_fixture_only') is not False):
        raise ValueError('run identity or mode mismatch')
    private = run_root / 'host_private/archive'
    sources = {}

    def load(name: str, path: Path) -> list[dict]:
        result, info = rows(path, run_root)
        sources[name] = info
        return result

    gap = load('gap_cycle', private / 'gap_cycle.jsonl')
    payload = load('memory_payload', private / 'memory_payload.jsonl')
    visible = load('gap_visible_transport', private / 'gap_visible_transport.jsonl')
    transport = load('memory_transport', private / 'memory_transport.jsonl')
    events = load('memory_events', private / 'events.jsonl')
    task_paths = list((run_root / 'jobs').glob('*/*/agent/research_events.jsonl'))
    if len(task_paths) != 1:
        raise ValueError('Task event source not unique')
    task = load('task_events', task_paths[0])
    trajectory_path = private / 'trajectory_memory.json'
    trajectory = json.loads(trajectory_path.read_bytes())
    sources['trajectory'] = {'file': trajectory_path.relative_to(run_root).as_posix(),
        'bytes': trajectory_path.stat().st_size, 'sha256': file_sha(trajectory_path),
        'rows': len(trajectory['steps'])}

    if len(gap) != 19 or len(payload) != 90 or len(visible) != 90 or len(transport) != 90:
        raise ValueError('completed run source counts changed')
    by_call = {}
    for items in (payload, visible):
        for entry in items:
            value = entry['value']
            key = (value['cycle_step'], value['call_sequence'], value['phase'])
            if key in by_call and ('request' if items is payload else 'response') in by_call[key]:
                raise ValueError('duplicate role call identity')
            by_call.setdefault(key, {})['request' if items is payload else 'response'] = entry
    if len(by_call) != 90 or any(set(value) != {'request', 'response'} for value in by_call.values()):
        raise ValueError('role request/response mismatch')
    if [x['value']['phase'] for x in transport] != [x['value']['phase'] for x in visible]:
        raise ValueError('transport phase order mismatch')
    transport_by_sequence = {n: entry for n, entry in enumerate(transport, 1)}
    steps = {item['step_count']: item for item in trajectory['steps']}
    cycle_output = []
    for entry in gap:
        value = entry['value']
        n = value['step']
        calls = []
        for (step, sequence, phase), pair in sorted(by_call.items()):
            if step != n:
                continue
            if transport_by_sequence[sequence]['value']['phase'] != phase:
                raise ValueError('transport phase differs from frozen call identity')
            request, response = pair['request'], pair['response']
            calls.append({'cycle_step': n, 'call_sequence': sequence, 'phase': phase,
                          'request_source': request['source'],
                          'response_source': response['source'],
                          'transport_source': transport_by_sequence[sequence]['source'],
                          'transport_status': transport_by_sequence[sequence]['value']['status'],
                          'actual_system': request['value']['system'],
                          'actual_prompt': request['value']['prompt'],
                          'visible_response_text': response['value']['content'],
                          'visible_tool_calls_as_recorded': response['value']['tool_calls']})
        selection = [call for call in calls if call['phase'] == 'selection']
        if len(selection) != 1 or steps[n]['user_prompt_phase2'] != selection[0]['actual_prompt']:
            raise ValueError('Phase 2 actual prompt does not match recorded send')
        if steps[n]['raw_response_phase2'] != selection[0]['visible_response_text']:
            raise ValueError('Phase 2 response does not match recorded visible text')
        cycle_output.append({'cycle_step': n, 'event_id': value['event_id'],
            'sequence': value['sequence'], 'gap_cycle_source': entry['source'],
            'trajectory_source': {'file': sources['trajectory']['file'],
                'step_index': n, 'step_canonical_sha256': sha(canonical(steps[n]))},
            'maintenance_operations_as_recorded': steps[n]['operations'],
            'review_and_stale_report': value['report'],
            'final_formal_gaps': value['formal_gaps'],
            'phase2_should_inject': steps[n]['should_inject'],
            'phase2_context_for_action': steps[n]['context_for_action'],
            'actual_role_calls': calls})

    task_by_kind = {}
    for entry in task:
        task_by_kind.setdefault(entry['value']['event_type'], []).append(entry)
    ready = task_by_kind['provider_request_ready']
    content_by_call = {e['value']['llm_call_id']: e for e in task_by_kind['provider_response_content']}
    action_by_call = {e['value']['llm_call_id']: e for e in task_by_kind['action_selected']}
    response_by_call = {e['value']['llm_call_id']: e for e in task_by_kind['provider_response']}
    attempt_by_call = {e['value']['llm_call_id']: e for e in task_by_kind['provider_request_attempt']}
    if len(ready) != 19 or len(content_by_call) != 19:
        raise ValueError('Task call identity count mismatch')
    receipts = {}
    for turn, request in enumerate(ready, 1):
        messages = request['value']['payload']['content']['messages']
        for message_index, message in enumerate(messages):
            for block_index, block in enumerate(message.get('content', [])):
                if isinstance(block, dict) and block.get('type') == 'tool_result':
                    tool_id = block['tool_use_id']
                    receipts.setdefault(tool_id, []).append({'first_visible_turn': turn,
                        'request_source': request['source'],
                        'request_event_id': request['value']['event_id'],
                        'message_index': message_index, 'block_index': block_index,
                        'tool_result_block': block})
    task_output = []
    for turn, request in enumerate(ready, 1):
        row = request['value']
        call_id = row['llm_call_id']
        visible_response = content_by_call[call_id]
        blocks = visible_response['value']['payload']['parsed_visible_blocks']
        tool_receipts = []
        for block in blocks:
            if block.get('type') != 'tool_use':
                continue
            possible = [item for item in receipts.get(block['id'], [])
                        if item['first_visible_turn'] > turn]
            if not possible:
                raise ValueError(f'no Task-visible tool receipt for {block["id"]}')
            tool_receipts.append(possible[0])
        request_content = dict(row['payload']['content'])
        request_content.pop('metadata', None)  # provider/session identity is not Task text
        hidden_blocks = 0
        public_messages = []
        for message in request_content['messages']:
            shown = []
            for block in message['content']:
                if isinstance(block, dict) and block.get('type') in {
                        'thinking', 'redacted_thinking', 'reasoning'}:
                    hidden_blocks += 1
                    continue
                shown.append(block)
            public_messages.append({**message, 'content': shown})
        request_content['messages'] = public_messages
        task_output.append({'task_turn': turn, 'llm_call_id': call_id,
            'request_event_id': row['event_id'], 'request_source': request['source'],
            'original_full_request_sha256': row['payload']['sha256'],
            'original_content_availability': row['payload']['content_availability'],
            'task_visible_request_except_private_metadata_and_hidden_blocks': request_content,
            'hidden_request_blocks_omitted': hidden_blocks,
            'reminder_event_id_in_request': row['payload'].get('pma_reminder_event_id'),
            'pma_event_id_in_request': row['payload'].get('pma_event_id'),
            'attempt_event': attempt_by_call[call_id]['value']['event_id'],
            'attempt_source': attempt_by_call[call_id]['source'],
            'response_event': response_by_call[call_id]['value']['event_id'],
            'provider_response_source': response_by_call[call_id]['source'],
            'response_source': visible_response['source'],
            'visible_response_blocks': blocks,
            'hidden_thinking_excluded_at_capture': visible_response['value']['payload'].get('hidden_thinking_excluded'),
            'action_selected': action_by_call[call_id]['value']['payload']
                if call_id in action_by_call else None,
            'action_source': action_by_call[call_id]['source']
                if call_id in action_by_call else None,
            'matched_tool_receipts_from_later_Task_request': tool_receipts})

    reminders = []
    for entry in events:
        value = entry['value']
        if not value.get('result', {}).get('reminder'):
            continue
        event_id = value['event']['event_id']
        matches = [item for item in task_output if item['pma_event_id_in_request'] == event_id]
        if len(matches) != 1:
            raise ValueError('selected reminder not in exactly one Task request')
        matched = matches[0]
        body = value['result']['reminder']
        if not any(body in text for text in visible_strings(
                matched['task_visible_request_except_private_metadata_and_hidden_blocks'])):
            raise ValueError('reminder body not present in recorded Task request')
        appended = [item for item in task_by_kind['pma_reminder_appended']
                    if item['value']['payload']['pma_event_id'] == event_id]
        if len(appended) != 1 or appended[0]['value']['event_id'] != matched['reminder_event_id_in_request']:
            raise ValueError('reminder append and Task request identities differ')
        reminders.append({'pma_event_id': event_id, 'actor_attempt': value['event']['actor_attempt'],
            'selected_source': entry['source'], 'reminder_body_as_recorded': body,
            'append_event_id': appended[0]['value']['event_id'],
            'append_source': appended[0]['source'],
            'task_turn': matched['task_turn'], 'task_llm_call_id': matched['llm_call_id'],
            'task_request_event_id': matched['request_event_id'],
            'task_request_source': matched['request_source'],
            'response_event_id': matched['response_event'],
            'subsequent_visible_response_blocks': matched['visible_response_blocks'],
            'subsequent_tool_receipts': matched['matched_tool_receipts_from_later_Task_request']})
    if len(reminders) != 3:
        raise ValueError('reminder count differs from recorded delivery')

    output.mkdir(parents=True, exist_ok=False)
    sanitizer = Sanitizer(secrets)
    public_files = [write_rows(output / 'cycles.jsonl', cycle_output, sanitizer),
                    write_rows(output / 'task_turns.jsonl', task_output, sanitizer),
                    write_rows(output / 'reminders.jsonl', reminders, sanitizer)]
    public_text = b''.join((output / item['file']).read_bytes() for item in public_files)
    if (any(secret.encode('utf-8') in public_text for secret in secrets) or
            BEARER.search(public_text.decode('utf-8')) or
            KEY.search(public_text.decode('utf-8')) or
            URL.search(public_text.decode('utf-8')) or
            THINKING_TAG.search(public_text.decode('utf-8'))):
        raise ValueError('sensitive marker remains in public projection')
    index = {'schema': 'pma-gap-visible-readonly-audit-v1', 'run_id': run_id,
        'source_kind': 'private_original_bytes', 'public_kind': 'allowlisted_redacted_jsonl',
        'sources': sources, 'public_files': public_files,
        'excluded_or_replaced': sanitizer.removals,
        'never_selected_fields': ['trajectory_memory.reasoning_phase1',
            'trajectory_memory.reasoning_phase2', 'provider_request_ready.provider_url',
            'provider_request_ready.content.metadata', 'private_profiles',
            'provider_request_ready.content.messages[*].content[type=thinking|redacted_thinking|reasoning]',
            'raw_http_headers', 'verifier_scripts_and_hidden_test_output'],
        'counts': {'cycles': len(cycle_output), 'role_calls': len(by_call),
                   'task_turns': len(task_output), 'reminders': len(reminders)}}
    (output / 'INDEX.json').write_bytes(canonical(index) + b'\n')
    return {'run_id': run_id, 'counts': index['counts'],
            'replacement_events': len(sanitizer.removals),
            'public_files': [(item['file'], item['bytes']) for item in public_files]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    args = parser.parse_args()
    result = export(args.run_root, args.output,
                    private_values(args.task_profile, args.pma_profile), args.run_id)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
