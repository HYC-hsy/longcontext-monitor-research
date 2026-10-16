"""Post-run, allowlisted public projection of an ordered GA/PMA selection.

This does not touch a running agent or the private originals. Unknown record
shapes and arbitrary logs are indexed by hash, not copied to the public tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from .archive_live_six_task import private_values


HIDDEN_KEYS = frozenset({
    'thinking', 'redacted_thinking', 'reasoning_content', 'signature',
    'thinking_signature', 'encrypted_content', 'encrypted_payload',
})
SENSITIVE_KEYS = frozenset({
    'api_key', 'access_token', 'authorization', 'password', 'credential',
    'client_secret', 'private_key', 'provider_url', 'api_base', 'base_url',
})
SUSPICIOUS_TEXT = re.compile(
    r'(?i)(?:<\s*(?:thinking|redacted_thinking)\s*>|'
    r'"(?:redacted_thinking|reasoning_content|encrypted_content|signature)"\s*:|'
    r'\bBearer\s+[A-Za-z0-9._~/+=-]{12,}|\bsk-[A-Za-z0-9_-]{12,}|'
    r'\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\s*[:=]\s*'
    r'["\']?[A-Za-z0-9._~/+=-]{12,})')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(value: object) -> dict:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return {'private_bytes': len(raw), 'private_sha256': hashlib.sha256(raw).hexdigest()}


class Projector:
    def __init__(self, secrets: list[str]):
        self.secrets = [item for item in secrets if len(item) >= 6]
        self.exclusions: list[dict] = []

    def excluded(self, value: object, reason: str, where: str) -> dict:
        result = {'excluded': reason, **identity(value)}
        self.exclusions.append({'where': where, **result})
        return result

    def text(self, value: object, where: str) -> str | dict:
        if not isinstance(value, str):
            return self.excluded(value, 'not_plain_text', where)
        if (any(secret in value for secret in self.secrets) or
                SUSPICIOUS_TEXT.search(value) or '\x00' in value or
                value.lstrip().startswith(('data:', 'event:'))):
            return self.excluded(value, 'sensitive_or_transport_text', where)
        return value

    def json_value(self, value: object, where: str) -> object:
        if isinstance(value, dict):
            output = {}
            for number, (key, item) in enumerate(value.items()):
                if not isinstance(key, str):
                    return self.excluded(value, 'non_string_key', where)
                child = f'{where}.member[{number}]'
                if isinstance(self.text(key, child + '.name'), dict):
                    output[f'excluded_key_{number}'] = self.excluded(
                        item, 'private_key_name', child)
                    continue
                if key.lower() in HIDDEN_KEYS | SENSITIVE_KEYS:
                    output[key] = self.excluded(item, 'private_field', child)
                else:
                    output[key] = self.json_value(item, child)
            return output
        if isinstance(value, list):
            return [self.json_value(item, f'{where}[{n}]') for n, item in enumerate(value)]
        if isinstance(value, str):
            return self.text(value, where)
        if value is None or type(value) in (int, float, bool):
            return value
        return self.excluded(value, 'unsupported_json_value', where)

    def block(self, block: object, where: str) -> dict:
        if not isinstance(block, dict):
            return self.excluded(block, 'unsupported_content_block', where)
        kind = block.get('type')
        if kind == 'text' and isinstance(block.get('text'), str):
            return {'type': 'text', 'text': self.text(block['text'], where + '.text')}
        if kind == 'tool_use' and all(isinstance(block.get(k), str) for k in ('id', 'name')):
            return {'type': 'tool_use', 'id': block['id'], 'name': block['name'],
                    'input': self.json_value(block.get('input'), where + '.input')}
        if kind == 'tool_result' and isinstance(block.get('tool_use_id'), str):
            content = block.get('content')
            if isinstance(content, str):
                shown = self.text(content, where + '.content')
            elif isinstance(content, list):
                shown = [self.block(item, f'{where}.content[{n}]')
                         for n, item in enumerate(content)]
            else:
                shown = self.excluded(content, 'unsupported_tool_result', where + '.content')
            return {'type': 'tool_result', 'tool_use_id': block['tool_use_id'],
                    'content': shown}
        return self.excluded(block, 'hidden_or_unknown_block', where)

    def request(self, value: object, where: str) -> dict:
        if not isinstance(value, dict) or not isinstance(value.get('messages'), list):
            return self.excluded(value, 'unsupported_request_shape', where)
        output = {key: value.get(key) for key in ('model', 'max_tokens', 'stream')}
        setting = value.get('thinking')
        if (isinstance(setting, dict) and set(setting) <= {'type', 'budget_tokens'} and
                setting.get('type') in {'adaptive', 'enabled', 'disabled'}):
            output['thinking_setting'] = setting
        output['system'] = [self.block(block, f'{where}.system[{n}]')
                            for n, block in enumerate(value.get('system', []))]
        output['messages'] = []
        for n, msg in enumerate(value['messages']):
            if (not isinstance(msg, dict) or msg.get('role') not in {'user', 'assistant'} or
                    not isinstance(msg.get('content'), list)):
                output['messages'].append(self.excluded(msg, 'unsupported_message',
                                                       f'{where}.messages[{n}]'))
                continue
            output['messages'].append({'role': msg['role'], 'content': [
                self.block(block, f'{where}.messages[{n}].content[{j}]')
                for j, block in enumerate(msg['content'])]})
        output['tools'] = []
        for n, tool in enumerate(value.get('tools', [])):
            if not isinstance(tool, dict) or not isinstance(tool.get('name'), str):
                output['tools'].append(self.excluded(tool, 'unsupported_tool_schema',
                                                     f'{where}.tools[{n}]'))
                continue
            output['tools'].append({'name': tool['name'],
                'description': self.text(tool.get('description', ''), f'{where}.tools[{n}].description'),
                'input_schema': self.json_value(tool.get('input_schema'),
                                                 f'{where}.tools[{n}].input_schema')})
        return output


EVENT_FIELDS = {
    'history_transform_started': ('message_count', 'bytes', 'sha256'),
    'history_transform_finished': ('message_count', 'bytes', 'sha256', 'changed'),
    'provider_request_attempt': ('attempt',),
    'provider_response': ('attempt', 'status_code', 'outcome'),
    'provider_usage': ('api_mode', 'call_type', 'input_tokens', 'output_tokens',
                       'cached_input_tokens', 'cache_creation_input_tokens',
                       'cache_read_input_tokens'),
    'action_selected': ('provider_request_event_id', 'intervention_event_id',
                        'injection_occurrence_id', 'tool_names', 'tool_call_ids',
                        'response_sha256'),
    'pma_reminder_appended': ('actor_attempt', 'input_sent', 'pma_event_id',
                              'reminder_sha256'),
    'completion_proposal': ('proposal_id', 'origin', 'turn', 'response_sha256',
                            'response_preview', 'stop_reason'),
    'completion_decision': ('decision', 'reason_codes', 'next_prompt',
                            'target_obligation_ids', 'checker_ids', 'proposal_id'),
    'termination': ('result', 'data'),
}


def project_event(row: dict, projector: Projector, number: int) -> dict:
    kind = row.get('event_type')
    payload = row.get('payload')
    base = {key: row.get(key) for key in
            ('event_id', 'event_type', 'timestamp', 'task_id', 'run_id',
             'llm_call_id', 'trace_id', 'span_id')}
    if not isinstance(payload, dict):
        base['payload'] = projector.excluded(payload, 'unsupported_payload', f'event[{number}]')
    elif kind == 'provider_request_ready':
        base['payload'] = {key: payload.get(key) for key in
                           ('content_availability', 'sha256', 'bytes', 'model', 'stream',
                            'message_count', 'tool_count', 'max_retries', 'call_type',
                            'actor_attempt', 'pma_event_id', 'pma_reminder_event_id')}
        base['payload']['content'] = projector.request(payload.get('content'),
                                                        f'event[{number}].content')
    elif kind == 'provider_response_content':
        base['payload'] = {'attempt': payload.get('attempt'),
            'hidden_thinking_excluded': payload.get('hidden_thinking_excluded'),
            'parsed_visible_blocks': [projector.block(item, f'event[{number}].visible[{n}]')
                for n, item in enumerate(payload.get('parsed_visible_blocks', []))]}
    elif kind in EVENT_FIELDS:
        base['payload'] = {key: projector.json_value(payload.get(key),
            f'event[{number}].{key}') for key in EVENT_FIELDS[kind]}
    else:
        base['payload'] = projector.excluded(payload, 'unsupported_event_type',
                                             f'event[{number}].payload')
    return base


def parse_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f'JSONL row {number} is not an object')
        rows.append(value)
    return rows


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def project_slot(directory: Path, target: Path, secrets: list[str]) -> dict:
    identity_record = json.loads((directory / 'run_identity.json').read_text(encoding='utf-8'))
    run_root = Path(identity_record['run_root']).resolve(strict=True)
    if not run_root.is_relative_to(directory.resolve(strict=True)):
        raise RuntimeError('run root escapes prepared slot')
    status = json.loads((run_root / 'archive/live_result.json').read_text(encoding='utf-8'))
    projector = Projector(secrets)
    sources = {}
    output = {}

    def emit(source: Path, name: str, value: object) -> None:
        sources[name] = {'private_relative_path': source.relative_to(directory).as_posix(),
                         'private_bytes': source.stat().st_size, 'private_sha256': digest(source)}
        destination = target / name
        write_json(destination, value)
        output[name] = {'public_bytes': destination.stat().st_size,
                        'public_sha256': digest(destination)}

    event_files = list((run_root / 'jobs').glob('*/*/agent/research_events.jsonl'))
    if len(event_files) != 1:
        raise RuntimeError('Task research event source is missing or ambiguous')
    events = parse_jsonl(event_files[0])
    emit(event_files[0], 'task_events_public.json', [
        project_event(row, projector, n) for n, row in enumerate(events, 1)])
    counts = {}
    usage = {key: 0 for key in ('input_tokens', 'output_tokens', 'cached_input_tokens',
              'cache_creation_input_tokens', 'cache_read_input_tokens')}
    seen_usage = set()
    tool_calls = 0
    terminal = None
    reminder_ready = set()
    attempted = set()
    responded = set()
    for row in events:
        kind, payload = row.get('event_type'), row.get('payload') or {}
        counts[kind] = counts.get(kind, 0) + 1
        if kind == 'provider_request_ready' and payload.get('pma_reminder_event_id'):
            reminder_ready.add(row.get('llm_call_id'))
        elif kind == 'provider_request_attempt':
            attempted.add(row.get('llm_call_id'))
        elif kind == 'provider_response':
            responded.add(row.get('llm_call_id'))
        if kind == 'provider_usage':
            for key in usage:
                if type(payload.get(key)) in (int, float):
                    usage[key] += payload[key]
                    seen_usage.add(key)
        if kind == 'action_selected':
            tool_calls += len(payload.get('tool_call_ids') or [])
        if kind == 'termination':
            terminal = payload.get('result')
    usage = {key: value if key in seen_usage else None for key, value in usage.items()}
    reminder_counts = {'selected_and_appended': counts.get('pma_reminder_appended', 0),
                       'present_in_request_ready': len(reminder_ready),
                       'present_at_provider_attempt': len(reminder_ready & attempted),
                       'present_with_provider_response': len(reminder_ready & responded)}

    phases = {}
    if status.get('condition') == 'B':
        base = run_root / 'host_private/archive'
        request_path = base / 'memory_payload.jsonl'
        phase_path = base / 'memory_transport.jsonl'
        trajectory_path = base / 'trajectory_memory.json'
        bank_path = base / 'memory.json'
        requests = parse_jsonl(request_path)
        emit(request_path, 'pma_requests_public.json', [{
            'phase': row.get('phase'), 'started_epoch': row.get('started_epoch'),
            'system': projector.text(row.get('system'), f'pma_request[{n}].system'),
            'prompt': projector.text(row.get('prompt'), f'pma_request[{n}].prompt'),
            'tools': projector.json_value(row.get('tools'), f'pma_request[{n}].tools')}
            for n, row in enumerate(requests, 1)])
        transport = parse_jsonl(phase_path)
        emit(phase_path, 'pma_transport_public.json', [{key: row.get(key) for key in
            ('phase', 'started_epoch', 'ended_epoch', 'status')}
            for row in transport])
        for row in transport:
            key = f"{row.get('phase')}:{row.get('status')}"
            phases[key] = phases.get(key, 0) + 1
        trajectory = json.loads(trajectory_path.read_text(encoding='utf-8'))
        emit(trajectory_path, 'pma_steps_public.json', [{
            **{key: row.get(key) for key in ('step_id', 'timestamp', 'trigger_step',
                                             'step_count', 'observation_len', 'should_inject')},
            'operations': [{key: projector.json_value(op.get(key),
                f'pma_step[{n}].operation[{j}].{key}') for key in
                ('action', 'memory_id', 'content', 'success', 'error')}
                for j, op in enumerate(row.get('operations', []))],
            'context_for_action': projector.text(row.get('context_for_action'),
                                                  f'pma_step[{n}].context_for_action'),
            'raw_response_phase1': projector.text(row.get('raw_response_phase1'),
                                                  f'pma_step[{n}].phase1'),
            'raw_response_phase2': projector.text(row.get('raw_response_phase2'),
                                                  f'pma_step[{n}].phase2'),
            'memory_snapshot': {key: row.get('memory_snapshot', {}).get(key) for key in
                                ('status', 'knowledge_count', 'procedural_count')}}
            for n, row in enumerate(trajectory.get('steps', []), 1)])
        bank = json.loads(bank_path.read_text(encoding='utf-8'))
        emit(bank_path, 'pma_final_bank_public.json', {
            'status': projector.text(bank.get('status'), 'pma_bank.status'),
            **{kind: [{'id': item.get('id'), 'content': projector.text(item.get('content'),
                f'pma_bank.{kind}[{n}].content')} for n, item in enumerate(bank.get(kind, []))]
                for kind in ('knowledge', 'procedural')}})

    native = status.get('native_result') or {}
    reports_file = run_root / 'archive/native_reports_checked.json'
    reports = json.loads(reports_file.read_text(encoding='utf-8'))
    report_summaries = []
    for report in reports.get('reports', []):
        source_name = Path(report['source']).name
        paths = list((run_root / 'jobs').glob(f'*/*/verifier/{source_name}'))
        if len(paths) == 1:
            parsed = json.loads(paths[0].read_text(encoding='utf-8'))
            summary = (parsed.get('results') or {}).get('summary') or {}
            report_summaries.append({'source': source_name,
                'private_sha256': digest(paths[0]),
                'summary': {key: summary.get(key) for key in
                            ('tests', 'passed', 'failed', 'skipped', 'pending', 'other')},
                'registered_sha256': report.get('sha256'),
                'present_parseable_executed': report.get('present_parseable_executed')})
        else:
            report_summaries.append({'source': source_name, 'availability': 'ambiguous_or_missing'})
    row = {'run_id': status.get('run_id'), 'task': status.get('task'),
           'condition': status.get('condition'), 'zero_model_fixture_only':
           status.get('zero_model_fixture_only'), 'harbor_return_code':
           status.get('harbor_return_code'), 'primary_failure':
           projector.json_value(status.get('primary_failure'), 'status.primary_failure'), 'worker_return_code':
           status.get('worker_return_code'), 'pma_finalization':
           projector.json_value(status.get('pma_finalization'), 'status.pma_finalization'), 'cleanup_confirmed':
           status.get('cleanup_confirmed'), 'remaining_containers':
           projector.json_value(status.get('remaining_containers'), 'status.remaining_containers'), 'cleanup_errors':
           projector.json_value(status.get('cleanup_errors'), 'status.cleanup_errors'), 'native_status': native.get('status'),
           'native_reward': (native.get('rewards') or {}).get('reward'),
           'task_terminal': terminal,
           'agent_execution': native.get('agent_execution'),
           'verifier_execution': native.get('verifier'),
           'native_reports_checked': status.get('native_reports_checked'),
           'report_summaries': report_summaries, 'task_event_counts': counts,
           'task_tool_calls_selected': tool_calls, 'task_usage_visible': usage,
           'reminder_delivery_evidence': reminder_counts,
           'pma_phase_results': phases}
    emit(run_root / 'archive/live_result.json', 'mechanical_public.json', row)
    return {'summary': row, 'private_sources': sources, 'public_files': output,
            'field_exclusions': projector.exclusions}


def archive(root: Path, target: Path, secrets: list[str], run_commit: str) -> dict:
    root = root.resolve(strict=True)
    if target.exists():
        raise FileExistsError(target)
    selection = json.loads((root / 'selection_result.json').read_text(encoding='utf-8'))
    prepared = json.loads((root / 'selection_preparation.json').read_text(encoding='utf-8'))
    if selection.get('mode') != 'run' or prepared.get('mode') != 'prepare':
        raise RuntimeError('selection receipts are not a prepare-then-run pair')
    target.mkdir(parents=True)
    summary = []
    source_index = {}
    output_index = {}
    exclusions = []
    for prepared_row in prepared['slots']:
        order = prepared_row['order']
        original = next((row for row in selection['slots'] if row['order'] == order), None)
        directory = root / f"{order:02d}-{prepared_row['task']}-{prepared_row['condition']}-r{prepared_row['occurrence']}"
        if original is None or original.get('result', {}).get('arm') is None:
            summary.append({'order': order, 'task': prepared_row['task'],
                'condition': prepared_row['condition'],
                'status': original.get('status') if original else 'not_started'})
            continue
        projected = project_slot(directory, target / f'{order:02d}', secrets)
        row = {'order': order, 'occurrence': prepared_row['occurrence'],
               'disposition': original['result']['arm']['disposition'],
               **projected['summary']}
        summary.append(row)
        for name, value in projected['private_sources'].items():
            source_index[f'{order:02d}/{name}'] = value
        for name, value in projected['public_files'].items():
            output_index[f'{order:02d}/{name}'] = value
        exclusions.extend({'order': order, **item} for item in projected['field_exclusions'])
    write_json(target / 'SUMMARY.json', {'schema': 'pma-ga-ordered-postrun-public-v1',
        'run_code_commit': run_commit, 'slots': summary,
        'remaining_not_started': selection.get('remaining_not_started', [])})
    write_json(target / 'PRIVATE_SOURCE_INDEX.json', source_index)
    write_json(target / 'FIELD_EXCLUSIONS.json', exclusions)
    excluded_files = []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.name in {'research_events.jsonl', 'memory_payload.jsonl',
                         'memory_transport.jsonl', 'trajectory_memory.json',
                         'memory.json', 'live_result.json'}:
            continue
        excluded_files.append({'private_relative_path': relative,
            'bytes': path.stat().st_size, 'sha256': digest(path),
            'reason': 'raw_or_unsupported_file_not_publicly_projected'})
    write_json(target / 'EXCLUDED_PRIVATE_FILES.json', excluded_files)
    index = {}
    for path in sorted(target.rglob('*')):
        if path.is_file() and path.name != 'PUBLIC_FILE_HASHES.json':
            index[path.relative_to(target).as_posix()] = {'bytes': path.stat().st_size,
                                                             'sha256': digest(path)}
    write_json(target / 'PUBLIC_FILE_HASHES.json', index)
    return {'slots': len(summary), 'public_files': len(index),
            'excluded_private_files': len(excluded_files), 'excluded_fields': len(exclusions)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--public-root', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    parser.add_argument('--run-code-commit', required=True)
    args = parser.parse_args()
    result = archive(args.private_root, args.public_root,
                     private_values(args.task_profile, args.pma_profile),
                     args.run_code_commit)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
