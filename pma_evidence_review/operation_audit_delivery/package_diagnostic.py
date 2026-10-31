"""Whitelist-only publication of the first reviewer-only diagnosis."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import zipfile


def digest(data):
    return sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--private-results', required=True)
    parser.add_argument('--test-records', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    private = Path(args.private_results).resolve()
    tests = Path(args.test_records).resolve()
    out = Path(args.out).resolve()
    if out.exists() or out.with_suffix('.index.json').exists():
        raise ValueError('publication_target_exists')
    selection = {
        'README.md': root / 'pma_evidence_review/operation_audit_delivery/REAL_DIAGNOSTIC.md',
        'inputs/historical_path_material.json': root / 'pma_evidence_review/operation_audit_delivery/historical_path_material.json',
        'inputs/frozen_replay_cases.json': root / 'pma_evidence_review/operation_audit_delivery/frozen_replay_cases.json',
        'real/frozen_inputs_and_plan.json': private / 'frozen_inputs_and_plan.json',
        'real/reference_labels_development_only.json': private / 'reference_labels_development_only.json',
        'real/requests.jsonl': private / 'requests.jsonl',
        'real/responses.jsonl': private / 'responses.jsonl',
        'real/results.json': private / 'results.json',
        'real/run_identity.json': private / 'run_identity.json',
        'real/stop_state.json': private / 'stop_state.json',
        'tests/affected-tests.txt': tests / 'affected-tests.txt',
        'tests/affected-tests-exit.txt': tests / 'affected-tests-exit.txt',
        'tests/prototype-tests.txt': tests / 'prototype-tests.txt',
        'tests/prototype-tests-exit.txt': tests / 'prototype-tests-exit.txt',
    }
    secret = re.compile(rb'(?i)(authorization\s*[:=]|bearer\s+\S+|api_?key\s*[:=]|apikey\s*[:=]|https?://[^\s/@]+:[^\s/@]+@)')
    payloads = {}
    rows = []
    for name, path in selection.items():
        data = path.read_bytes()
        if secret.search(data):
            raise ValueError('secret_pattern_in_' + name)
        payloads[name] = data
        rows.append({'path': name, 'bytes': len(data), 'sha256': digest(data),
                     'origin': 'public_source' if name.startswith('inputs/') or name == 'README.md'
                     else 'private_run_public_projection'})
    index = {'schema': 'operation-audit-diagnostic-package-v1',
             'execution_code_sha': 'a0f35e1ab4586472ebc0768b87e3cc228f36aa14',
             'archive_content': 'three reviewer-only calls; no splitter, Task, evaluator or memory write',
             'redaction': 'none; explicit whitelist excludes profile, endpoint, credentials, private_client, hidden reasoning and hidden tests',
             'missing': [], 'files': rows}
    index_bytes = (json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
        archive.writestr('PACKAGE_INDEX.json', index_bytes)
    with zipfile.ZipFile(out) as archive:
        if archive.testzip() is not None:
            raise ValueError('zip_crc')
        for name, data in {**payloads, 'PACKAGE_INDEX.json': index_bytes}.items():
            if archive.read(name) != data:
                raise ValueError('zip_payload_mismatch_' + name)
    outer = {'zip_file': out.name, 'zip_bytes': out.stat().st_size,
             'zip_sha256': digest(out.read_bytes()), 'files_including_index': len(rows) + 1,
             'package_index_sha256': digest(index_bytes)}
    out.with_suffix('.index.json').write_text(json.dumps(outer, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(outer, sort_keys=True))


if __name__ == '__main__':
    main()
