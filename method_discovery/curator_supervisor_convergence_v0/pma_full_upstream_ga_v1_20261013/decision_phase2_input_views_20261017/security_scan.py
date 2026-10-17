"""Post-run public-delivery scan; never prints or serializes private secrets."""

from __future__ import annotations

import json
from pathlib import Path
import re
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
PROFILE = Path('E:/LongContext/monitor_config/models.local.json')
SENSITIVE = re.compile(rb'(?i)(?:sk-[a-z0-9]{12,}|bearer\s+[a-z0-9._-]{12,}|'
                       rb'redacted_thinking|encrypted_payload|"signature"\s*:)')


def scan() -> dict:
    profile = json.loads(PROFILE.read_text(encoding='utf-8'))['claude_monitor_opus48']
    secrets = [profile[key].encode('utf-8') for key in ('apikey', 'apibase')]
    checked = 0
    actual_secret_hits = []
    pattern_hits = []
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or path.name == 'PUBLIC_SECURITY_SCAN.json':
            continue
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        entries = []
        if path.suffix == '.zip':
            with ZipFile(path) as bundle:
                entries = [(path.relative_to(HERE).as_posix() + ':' + name,
                            bundle.read(name)) for name in bundle.namelist()]
        else:
            entries = [(path.relative_to(HERE).as_posix(), path.read_bytes())]
        for name, raw in entries:
            checked += 1
            if any(secret and secret in raw for secret in secrets):
                actual_secret_hits.append(name)
            if SENSITIVE.search(raw):
                pattern_hits.append(name)
    report = {'checked_entries': checked, 'actual_private_profile_value_hits':
              actual_secret_hits, 'sensitive_pattern_hits': pattern_hits,
              'note': 'Pattern matches require manual review; this scan is not a proof '
                      'against every possible unknown secret.'}
    (HERE / 'PUBLIC_SECURITY_SCAN.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(scan(), ensure_ascii=False))
