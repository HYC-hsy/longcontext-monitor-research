"""Fail-closed public projection for two stopped, non-JSON run logs only.

This is a supplemental archive. It never changes the original run or the
previous public FILE_HASHES.json and never resumes an agent or evaluator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import private_values
from method_discovery.pos_upstream_ga_v1_20261017.collect_native_shared import secrets_from_profile


URL = re.compile(r"(?i)\b(?:https?|wss?)://[^\s<>\"'`]+")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}=?=?")
KEY = re.compile(r"(?i)\b(?:sk|pk)-[A-Za-z0-9_-]{12,}\b")
ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*"
    r"(?:['\"])?[^\s,'\"}]{6,}"
)
WINDOWS_PATH = re.compile(r"(?i)\b[A-Z]:\\[^\s\"'<>]+")
HIDDEN = re.compile(
    r"(?i)(?:<\s*(?:think|thinking|redacted_thinking)\b|"
    r"\b(?:redacted_thinking|reasoning_content|encrypted_content|thinking_signature)\b)"
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def project(raw: bytes, secrets: list[str]) -> tuple[bytes, dict[str, int]]:
    text = raw.decode('utf-8')  # Decode failures must stop this public export.
    if any(ord(char) < 32 and char not in '\r\n\t' for char in text):
        raise ValueError('unhandled control character in plain log')
    counts = {'hidden_lines_omitted': 0, 'profile_values': 0, 'urls': 0,
              'emails': 0, 'bearer': 0, 'keys': 0, 'assignments': 0,
              'windows_paths': 0}
    output = []
    for raw_line in text.splitlines(keepends=True):
        if HIDDEN.search(raw_line):
            counts['hidden_lines_omitted'] += 1
            ending = '\r\n' if raw_line.endswith('\r\n') else ('\n' if raw_line.endswith('\n') else '')
            output.append('[REDACTED_HIDDEN_LINE_SHA256:' + sha(raw_line.encode('utf-8'))[:16] + ']' + ending)
            continue
        line = raw_line
        for secret in secrets:
            if secret and secret in line:
                counts['profile_values'] += line.count(secret)
                line = line.replace(secret, '[REDACTED_PRIVATE_CONFIG]')
        for name, pattern, label in (
            ('urls', URL, 'URL'), ('emails', EMAIL, 'EMAIL'),
            ('bearer', BEARER, 'AUTH'), ('keys', KEY, 'KEY'),
            ('assignments', ASSIGNMENT, 'CREDENTIAL'),
            ('windows_paths', WINDOWS_PATH, 'LOCAL_PATH'),
        ):
            def replace(match: re.Match[str]) -> str:
                counts[name] += 1
                return '[REDACTED_' + label + '_SHA256:' + sha(match.group().encode('utf-8'))[:16] + ']'
            line = pattern.sub(replace, line)
        output.append(line)
    public = ''.join(output)
    if (HIDDEN.search(public) or URL.search(public) or EMAIL.search(public) or
            BEARER.search(public) or KEY.search(public) or
            ASSIGNMENT.search(public) or WINDOWS_PATH.search(public) or
            any(secret in public for secret in secrets if secret)):
        raise ValueError('plain log projection did not remove a private marker')
    return public.encode('utf-8'), counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--task-profile', type=Path, required=True)
    parser.add_argument('--pma-profile', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    identity = json.loads((source / 'run_identity.json').read_text(encoding='utf-8'))
    run = Path(identity['run_root']).resolve(strict=True)
    if not run.is_relative_to(source) or run.name != identity['run_id']:
        raise ValueError('run root differs from stopped source identity')
    if (source / 'authorization.json').exists() or not (source / 'batch_result.json').is_file():
        raise ValueError('run is active or final result is unavailable')
    trials = [path for path in (run / 'jobs').glob('*/*')
              if (path / 'agent/task_terminal.json').is_file()]
    if len(trials) != 1:
        raise ValueError('Task trial terminal is not unique')
    selected = {
        'pos/events.stderr.log': run / 'control/pos_archive/events.stderr.log',
        'task/agent/agent_stdout.log': trials[0] / 'agent/agent_stdout.log',
    }
    secrets = sorted(set(secrets_from_profile(args.task_profile) +
                         private_values(args.task_profile, args.pma_profile)),
                     key=len, reverse=True)
    prepared = []
    for name, path in selected.items():
        raw = path.read_bytes()
        data, counts = project(raw, secrets)
        prepared.append((name, raw, data, counts))
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, raw, data, counts in prepared:
        target = args.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        if target.read_bytes() != data:
            raise RuntimeError('public plain log readback differs')
        rows.append({'path': name, 'source_bytes': len(raw),
                     'source_sha256': sha(raw), 'public_bytes': len(data),
                     'public_sha256': sha(data), 'redactions': counts,
                     'source_line_count': len(raw.decode('utf-8').splitlines()),
                     'public_line_count': len(data.decode('utf-8').splitlines())})
    index = args.output / 'FILE_HASHES.json'
    with index.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump({'schema': 'pos-pma-shared-view-plain-log-addendum-v1',
                   'run_id': identity['run_id'],
                   'previous_archive': 'raw_live_sqlite_contract_v2/FILE_HASHES.json',
                   'public_copy_is_source_byte_identical': False,
                   'files': rows}, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'run_id': identity['run_id'], 'files': len(rows),
                      'hidden_lines_omitted': sum(row['redactions']['hidden_lines_omitted'] for row in rows),
                      'index_sha256': sha(index.read_bytes())}))


if __name__ == '__main__':
    main()
