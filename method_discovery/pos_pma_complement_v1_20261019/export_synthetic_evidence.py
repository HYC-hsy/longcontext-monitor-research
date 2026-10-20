"""Export only the audited zero-model synthetic fixture; never publish profiles.

Creates a new directory and a line/file hash map. Every emitted event retains
the original source line. This is a derived public copy, not byte-identical raw.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


ROLE_EVENTS = {'pos_role_request', 'pos_role_response',
               'candidate_pma_request', 'candidate_pma_response',
               'belief_model_input', 'belief_sentinel_model_input',
               'belief_sentinel_progress_model_input', 'belief_text_updated',
               'shared_audit_history_input', 'shared_audit_source_projection'}
PRIVATE_KEYS = {'provider_url', 'metadata', 'authorization', 'headers',
                'api_key', 'apikey', 'signature', 'thinking_content'}
EXTERNAL_URL = re.compile(r'https?://(?!127\.0\.0\.1(?::|/)|localhost(?::|/))\S+', re.I)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def public(value):
    if isinstance(value, dict):
        return {key: public(item) for key, item in value.items()
                if key.lower() not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [public(item) for item in value]
    if isinstance(value, str):
        # A private route in model-visible content is a failed export, not a
        # string to replace silently within evidence presented as complete.
        if EXTERNAL_URL.search(value):
            raise ValueError('model-visible text contains an external URL')
    return value


def rows(path, selected):
    original = path.read_bytes()
    result = []
    for line_number, raw in enumerate(original.splitlines(), 1):
        item = json.loads(raw)
        event = item.get('event', item.get('event_type'))
        if event in selected:
            clean = public(item)
            if event == 'provider_request_ready':
                payload = clean['payload']
                clean = {'event_type': event, 'event_id': clean['event_id'],
                    'llm_call_id': clean['llm_call_id'],
                    'timestamp': clean['timestamp'],
                    'model_visible_payload': payload['content'],
                    'request_sha256': payload['sha256'],
                    'request_bytes': payload['bytes']}
            result.append({'source_line': line_number, 'record': clean})
    return result, {'source_path': str(path), 'source_bytes': len(original),
                    'source_sha256': sha(original), 'selected_records': len(result)}


def emit(path, data):
    encoded = b''.join((json.dumps(item, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')) + '\n').encode('utf-8') for item in data)
    path.write_bytes(encoded)
    return {'public_path': path.name, 'public_bytes': len(encoded),
            'public_sha256': sha(encoded)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.run_root.resolve(strict=True)
    output = args.output.resolve(strict=False)
    output.mkdir(parents=True, exist_ok=False)
    event_file = root / 'control/pos_archive/events.jsonl'
    research = list((root / 'jobs').rglob('agent/research_events.jsonl'))
    if len(research) != 1:
        raise RuntimeError('exactly one synthetic Task event file required')
    role_rows, role_source = rows(event_file, ROLE_EVENTS)
    task_rows, task_source = rows(research[0], {'provider_request_ready',
        'provider_request_attempt', 'provider_response', 'provider_response_outcome'})
    if not any(item['record'].get('event') == 'candidate_pma_request'
               for item in role_rows) or len([item for item in task_rows if
               item['record'].get('event_type') == 'provider_request_ready']) != 2:
        raise RuntimeError('not the complete two-request candidate synthetic fixture')
    files = [dict(source=role_source, **emit(output / 'role_events.jsonl', role_rows)),
             dict(source=task_source, **emit(output / 'task_events.jsonl', task_rows))]
    batch = root.parents[1] / 'batch_result.json'
    batch_data = batch.read_bytes()
    batch_public = public(json.loads(batch_data))
    result = root / 'control/pos_archive/events.result.json'
    result_data = result.read_bytes()
    result_public = public(json.loads(result_data))
    files.append(dict(source={'source_path': str(batch), 'source_bytes': len(batch_data),
        'source_sha256': sha(batch_data)}, **emit(output / 'batch_result.jsonl', [batch_public])))
    files.append(dict(source={'source_path': str(result), 'source_bytes': len(result_data),
        'source_sha256': sha(result_data)}, **emit(output / 'episode_result.jsonl', [result_public])))
    for name in ('manifest.json', 'execution_identity.json'):
        source = root.parents[1] / name
        original = source.read_bytes()
        files.append(dict(source={'source_path': str(source), 'source_bytes': len(original),
            'source_sha256': sha(original)}, **emit(output / (name + 'l'),
            [public(json.loads(original))])))
    index = {'schema': 'pos-pma-complement-synthetic-public-v1',
             'raw_run_root': str(root), 'redactions': sorted(PRIVATE_KEYS),
             'files': files, 'real_model_calls': 0, 'official_evaluator_calls': 0}
    (output / 'FILE_HASHES.json').write_text(json.dumps(index, ensure_ascii=False,
        indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
