"""Offline, byte-preserving archive of the completed six-unit run. Never calls a model."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PRIVATE = Path(r'E:\LongContext\consequence_three_case_live_20261017')
RESTORED = Path(r'E:\LongContext\consequence_handoff_recovery_20261017')
SOURCE_TXT = Path(r'D:\360MoveData\Users\hsy\Desktop\CONSEQUENCE_V0_COMPLETE_HANDOFF.txt')
OUT = HERE / 'evidence_archive_20261017'
RAW = OUT / 'raw'
EXPECTED_TXT_SHA256 = 'd4a20037300dab0afd8f8f028d7c49a88807b8382f6337d51dd48db05009c0c'
NAMES = ('requests.jsonl', 'responses.jsonl', 'result.json', 'bank_before.json',
         'bank_after.json', 'provider_attempts.jsonl')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def dump(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def walk(value, loc=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, loc + '/' + key)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, loc + '/' + str(i))
    else:
        yield loc, value


def scan(path, data):
    """Fail closed on credentials or private transport fields; do not filter task text."""
    text = data.decode('utf-8')
    objects = [json.loads(x) for x in text.splitlines()] if path.suffix == '.jsonl' else [json.loads(text)]
    for i, obj in enumerate(objects):
        if path.name == 'provider_attempts.jsonl' and 'request' in obj:
            allowed = {'model', 'max_tokens', 'temperature', 'thinking', 'reasoning_effort',
                       'timeout', 'messages', 'tools'}
            assert set(obj['request']) <= allowed, (path, i, set(obj['request']) - allowed)
        for pointer, value in walk(obj):
            key = pointer.rsplit('/', 1)[-1].lower()
            assert key not in {'authorization', 'api_key', 'apikey', 'access_token',
                               'secret', 'password', 'base_url', 'api_base', 'endpoint',
                               'cookie', 'set-cookie'}, (path, i, pointer)
            if isinstance(value, str):
                assert not re.search(r'(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}', value), (path, i, pointer)
                assert not re.search(r'\bsk-[A-Za-z0-9_-]{16,}', value), (path, i, pointer)
    return len(objects)


def finds(unit, token):
    hits = []
    for name in NAMES:
        p = unit / name
        for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if token.lower() in line.lower():
                hits.append(f'{p.name}:{i}')
    return hits


def main():
    assert PRIVATE.is_dir() and RESTORED.is_dir() and SOURCE_TXT.is_file()
    assert not (OUT / 'EVIDENCE_INDEX.json').exists(), 'archive already built; never overwrite'
    units = sorted(p for p in PRIVATE.iterdir() if p.is_dir())
    assert len(units) == 6
    expected_private = read_json(PRIVATE / 'PRIVATE_FILE_SHA256.json')
    assert len(expected_private['files']) == 39
    seen = set()
    source_files = []
    for unit in units:
        assert {p.name for p in unit.iterdir() if p.is_file()} == set(NAMES)
        source_files.extend(unit / name for name in NAMES)
    source_files += [PRIVATE / name for name in ('identity.json', 'summary.json', 'summary.jsonl',
                                                 'PRIVATE_FILE_SHA256.json')]
    assert len(source_files) == 40
    for source in source_files:
        data = source.read_bytes()
        scan(source, data)
        rel = source.relative_to(PRIVATE).as_posix()
        assert rel not in seen
        seen.add(rel)
        if rel in expected_private['files']:
            item = expected_private['files'][rel]
            assert item['bytes'] == len(data) and item['sha256'] == sha(data), rel

    handoff_bytes = SOURCE_TXT.read_bytes()
    handoff = json.loads(handoff_bytes)
    assert handoff['file_count'] == len(handoff['files']) == 37
    assert (HERE / 'CONSEQUENCE_V0_COMPLETE_HANDOFF.txt').read_bytes() == handoff_bytes
    restoration = []
    for item in handoff['files']:
        rel = Path(item['path'])
        assert not rel.is_absolute() and '..' not in rel.parts
        expected_bytes = item['utf8_text'].encode('utf-8')
        actual = (RESTORED / rel).read_bytes()
        restoration.append({'path': rel.as_posix(), 'expected_bytes': item['bytes'],
                            'actual_bytes': len(actual), 'expected_sha256': item['sha256'],
                            'actual_sha256': sha(actual),
                            'match': expected_bytes == actual and len(actual) == item['bytes']
                                     and sha(actual) == item['sha256']})
    assert all(row['match'] for row in restoration)

    RAW.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in source_files:
        rel = source.relative_to(PRIVATE)
        target = RAW / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if target.exists():
            assert target.read_bytes() == data, target
        else:
            target.write_bytes(data)
        assert target.read_bytes() == data
        copied.append({'path': rel.as_posix(), 'bytes': len(data), 'sha256': sha(data),
                       'source_sha256': sha(data), 'redactions': []})

    evidence = []
    for unit in units:
        req = lines(unit / 'requests.jsonl')
        resp = lines(unit / 'responses.jsonl')
        attempts = lines(unit / 'provider_attempts.jsonl')
        result = read_json(unit / 'result.json')
        before = read_json(unit / 'bank_before.json')
        after = read_json(unit / 'bank_after.json')
        assert len(req) == len(resp) == 2 and len(attempts) == 4
        assert req[0]['phase'] == 'phase1' and req[1]['phase'] == 'phase2'
        assert resp[0]['phase'] == 'phase1' and resp[1]['phase'] == 'phase2'
        assert len(result['operations']) == len(resp[0]['tool_calls'])
        proposals = []
        for i, call in enumerate(resp[0]['tool_calls']):
            args = call['arguments']
            if isinstance(args, str):
                args = json.loads(args)
            proposals.append({'index': i, 'tool': call['name'], 'arguments': args,
                              'receipt': result['operations'][i],
                              'proposal_location': 'responses.jsonl:1/tool_calls/' + str(i),
                              'receipt_location': 'result.json/operations/' + str(i)})
        statuses = [p['arguments'].get('content') for p in proposals
                    if p['tool'] == 'memory_update_status']
        proposed = statuses[-1] if statuses else None
        saved = after['status']
        phase2 = req[1]['prompt']
        status_check = {'proposed_length': len(proposed) if proposed is not None else None,
                        'saved_length': len(saved), 'proposed_equals_saved': proposed == saved,
                        'saved_is_truncated_proposal': proposed is not None and
                             len(proposed) > 2000 and saved == proposed[:2000] + '...',
                        'phase2_contains_exact_saved_status': f'<status>{saved}</status>' in phase2,
                        'phase2_contains_full_proposal': proposed is not None and proposed in phase2,
                        'phase2_prompt_location': 'requests.jsonl:2/prompt'}
        assert status_check['phase2_contains_exact_saved_status']
        if proposed is not None:
            assert proposed == saved or status_check['saved_is_truncated_proposal']
        evidence.append({'unit': unit.name, 'case': result['case'], 'arm': result['arm'],
                         'step': result['step'], 'phase1_proposals_and_receipts': proposals,
                         'bank_before_location': 'bank_before.json',
                         'bank_after_location': 'bank_after.json',
                         'status_check': status_check,
                         'phase2_raw_output': resp[1]['content'],
                         'phase2_raw_location': 'responses.jsonl:2/content',
                         'parsed_reminder': result['reminder'],
                         'parsed_location': 'result.json/reminder',
                         'provider_record_locations': ['provider_attempts.jsonl:1-4'],
                         'sampler_density_log_density_locations':
                             {token: finds(unit, token) for token in ('density function', 'dnorm(x, log=TRUE)', 'log(func(x_star))')}
                             if result['case'] == '07' else None,
                         'compressor_locations':
                             {token: finds(unit, token) for token in ('180', '0 bytes', 'full decode')}
                             if result['case'] == '14' else None})

    report = {'kind': 'offline_archive_only', 'new_model_calls': 0, 'new_task_runs': 0,
              'new_evaluator_runs': 0, 'run_identity': read_json(RAW / 'identity.json'),
              'actual_unit_order': [u.name for u in units],
              'original_plan_14_105': ['reflection', 'candidate'],
              'actual_14_105': ['candidate', 'reflection'],
              'input_txt': {'expected_sha256': EXPECTED_TXT_SHA256,
                            'actual_sha256': sha(handoff_bytes), 'match': sha(handoff_bytes) == EXPECTED_TXT_SHA256},
              'restored_file_count': len(restoration), 'restored_file_checks': restoration,
              'private_inventory': {'path': 'raw/PRIVATE_FILE_SHA256.json',
                                    'note': 'Post-run inventory, not an original model/provider receipt; relative names, byte counts and hashes only.'},
              'redactions': [], 'redaction_explanation':
                  'No fields removed: capture contains no credential, authentication header, private endpoint or secret field. Full task/model text retained.',
              'capture_gaps': [
                  'No separate operation-receipt file: actual PMA receipts are result.json/operations, with saved state in bank_after.json.',
                  'No lower-level provider/network retry log beyond provider_attempts.jsonl wrapper boundary.',
                  'No Task continuation, evaluator result, or reminder-delivery receipt: none was run or delivered in this screen.',
                  'The exact original chat authorization is not present as a public repository artifact; README locates a summary only.'
              ], 'units': evidence}
    dump(OUT / 'EVIDENCE_INDEX.json', report)
    inventory = {'kind': 'public_copy_actual_bytes', 'files': copied,
                 'redactions': [], 'file_count': len(copied)}
    dump(OUT / 'PUBLIC_FILE_SHA256.json', inventory)
    # Standalone UTF-8 JSON TXT; all raw file text, plus index and public inventory.
    txt_files = []
    for path in sorted([p for p in RAW.rglob('*') if p.is_file()] +
                       [OUT / 'EVIDENCE_INDEX.json', OUT / 'PUBLIC_FILE_SHA256.json']):
        data = path.read_bytes()
        txt_files.append({'path': path.relative_to(OUT).as_posix(), 'bytes': len(data),
                          'sha256': sha(data), 'utf8_text': data.decode('utf-8')})
    dump(OUT / 'CONSEQUENCE_THREE_CASE_PUBLIC_EVIDENCE.txt',
         {'format': 'consequence-three-case-public-evidence-v1', 'file_count': len(txt_files),
          'files': txt_files})
    print(json.dumps({'files': len(copied), 'units': len(evidence),
                      'restored_matches': sum(x['match'] for x in restoration),
                      'txt_actual_sha256': sha(handoff_bytes),
                      'archive_txt_sha256': sha((OUT / 'CONSEQUENCE_THREE_CASE_PUBLIC_EVIDENCE.txt').read_bytes()),
                      'proposed_status_checks': [x['status_check'] for x in evidence]}, indent=2))


if __name__ == '__main__':
    main()
