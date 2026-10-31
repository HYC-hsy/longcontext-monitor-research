"""Publish only whitelisted visible reviewer evidence and safe test records."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile


def h(data):
    return sha256(data).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--private-results', required=True)
    p.add_argument('--test-records', required=True)
    p.add_argument('--out', required=True)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    local = root / 'pma_evidence_review/execution_link_delivery'
    real, tests, target = (Path(args.private_results).resolve(),
                           Path(args.test_records).resolve(), Path(args.out).resolve())
    if target.exists() or target.with_suffix('.index.json').exists():
        raise ValueError('output_already_exists')
    selection = {
        'README.md': local / 'REAL_DIAGNOSTIC.md',
        'frozen/frozen_candidate_cases.json': local / 'fixtures/frozen_candidate_cases.json',
        'frozen/candidate_model_requests.json': local / 'fixtures/candidate_model_requests.json',
        'frozen/reference_labels_development_only.json': local / 'fixtures/reference_labels_development_only.json',
        'real/model_input_plan.json': real / 'model_input_plan.json',
        'real/requests.jsonl': real / 'requests.jsonl',
        'real/responses.jsonl': real / 'responses.jsonl',
        'real/results.json': real / 'results.json',
        'real/run_identity.json': real / 'run_identity.json',
        'real/stop_state.json': real / 'stop_state.json',
        'tests/prototype.stdout.txt': tests / 'prototype.stdout.txt',
        'tests/prototype.stderr.txt': tests / 'prototype.stderr.txt',
        'tests/prototype.exit.txt': tests / 'prototype.exit.txt',
        'tests/production.stdout.txt': tests / 'production.stdout.txt',
        'tests/production.stderr.txt': tests / 'production.stderr.txt',
        'tests/production.exit.txt': tests / 'production.exit.txt',
    }
    secret = re.compile(rb'(?i)(authorization\s*[:=]|bearer\s+\S+|api_?key\s*[:=]|apikey\s*[:=]|https?://[^\s/@]+:[^\s/@]+@|sk-[a-z0-9]{12,})')
    files, rows = {}, []
    for name, path in selection.items():
        data = path.read_bytes()
        if secret.search(data):
            raise ValueError('secret_pattern:' + name)
        files[name] = data
        rows.append({'path': name, 'bytes': len(data), 'sha256': h(data),
                     'kind': 'frozen_development_material_not_model_input'
                     if name.startswith('frozen/') else 'visible_run_or_test_record'})
    index = {'schema': 'execution-link-first-real-diagnostic-v1',
             'execution_code_sha': '7718a6a912a139494326715fc99dea1a0b98bbc8',
             'model_calls': 3, 'task_calls': 0, 'splitter_calls': 0,
             'missing': [], 'redaction': 'none in whitelist; private profile/client, host witness, hidden reasoning/tests excluded',
             'files': rows}
    index_bytes = (json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
        z.writestr('PACKAGE_INDEX.json', index_bytes)
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None:
            raise ValueError('bad_crc')
        for name, data in {**files, 'PACKAGE_INDEX.json': index_bytes}.items():
            if z.read(name) != data:
                raise ValueError('bad_member:' + name)
    outer = {'zip_file': target.name, 'zip_bytes': target.stat().st_size,
             'zip_sha256': h(target.read_bytes()), 'files_including_index': len(rows)+1,
             'package_index_sha256': h(index_bytes)}
    target.with_suffix('.index.json').write_text(json.dumps(outer, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(outer, sort_keys=True))


if __name__ == '__main__':
    main()
