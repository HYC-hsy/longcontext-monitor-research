"""Project selected stopped-run JSONL logs without publishing private originals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_live_six_task import private_values, redact
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.archive_ordered_real import HIDDEN_KEYS, Projector, SUSPICIOUS_TEXT


FILES = {
    'auxiliary_provider_events': 'host_private/archive/provider_events.jsonl',
    'auxiliary_role_calls': 'host_private/archive/role_calls.jsonl',
    'task_research_events': 'jobs/pma-6632777c561a4f88/public_task__cjrBwKQ/agent/research_events.jsonl',
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def remove_hidden_field_names(value: object) -> object:
    if isinstance(value, dict):
        return {(f'excluded_hidden_field_{number}' if key.lower() in HIDDEN_KEYS else key):
                remove_hidden_field_names(item)
                for number, (key, item) in enumerate(value.items())}
    if isinstance(value, list):
        return [remove_hidden_field_names(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-root', required=True, type=Path)
    parser.add_argument('--task-profile', required=True, type=Path)
    parser.add_argument('--aux-profile', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    secrets = private_values(args.task_profile, args.aux_profile)
    projector = Projector(secrets)
    args.output.mkdir(parents=True, exist_ok=True)
    index = {}
    for label, relative in FILES.items():
        source = args.run_root / relative
        raw = source.read_bytes()
        public_lines = []
        for number, line in enumerate(raw.splitlines(), 1):
            if not line:
                continue
            redacted, _ = redact(line, secrets)
            obj = json.loads(redacted)
            public = remove_hidden_field_names(
                projector.json_value(obj, f'{label}[{number}]'))
            public_lines.append(json.dumps(public, ensure_ascii=False, sort_keys=True))
        rendered = ('\n'.join(public_lines) + '\n').encode('utf-8')
        if any(secret.encode('utf-8') in rendered for secret in secrets):
            raise RuntimeError(f'private profile value remains in {label}')
        suspect = SUSPICIOUS_TEXT.search(rendered.decode('utf-8'))
        if suspect:
            label_hint = ('hidden_field_label' if 'signature' in suspect.group(0) or
                          'reasoning_content' in suspect.group(0) else
                          'other_sensitive_pattern')
            raise RuntimeError(f'suspicious public text remains in {label} '
                               f'at offset {suspect.start()} ({label_hint})')
        destination = args.output / f'{label}.public.jsonl'
        destination.write_bytes(rendered)
        index[label] = {'private_relative_path': relative,
                        'private_bytes': len(raw), 'private_sha256': sha(raw),
                        'public_file': destination.name,
                        'public_bytes': len(rendered), 'public_sha256': sha(rendered),
                        'rows': len(public_lines)}
    exclusions = json.dumps(projector.exclusions, ensure_ascii=False, sort_keys=True,
                            indent=2).encode('utf-8') + b'\n'
    (args.output / 'FIELD_EXCLUSIONS.json').write_bytes(exclusions)
    index['field_exclusions'] = {'count': len(projector.exclusions),
                                 'public_sha256': sha(exclusions)}
    (args.output / 'PUBLIC_PROJECTION_INDEX.json').write_text(
        json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        encoding='utf-8')
    print(json.dumps({name: {'rows': row.get('rows'),
                             'public_bytes': row.get('public_bytes')}
                      for name, row in index.items()}, sort_keys=True))


if __name__ == '__main__':
    main()
