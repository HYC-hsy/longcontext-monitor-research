"""Compare captured synthetic A/B Task requests without broad normalization."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _request(run: Path, number: int) -> dict:
    path = run / 'archive/fake_provider_requests' / f'{number:04d}.json'
    return json.loads(path.read_text(encoding='utf-8'))


def _sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def compare(a: Path, b: Path) -> dict:
    first_a, first_b = _request(a, 1), _request(b, 1)
    if first_a['route'] != first_b['route'] or first_a['path'] != first_b['path']:
        raise RuntimeError('synthetic first route/path differs')
    body_a, body_b = first_a['body'], first_b['body']
    keys = sorted(set(body_a) | set(body_b))
    fields = {key: {'equal': body_a.get(key) == body_b.get(key),
                    'a_sha256': _sha(body_a.get(key)),
                    'b_sha256': _sha(body_b.get(key))}
              for key in keys}
    differences = [key for key, row in fields.items() if not row['equal']]
    second_b = _request(b, 2)
    reminder_visible = 'Offline PMA reminder.' in json.dumps(
        second_b['body'], ensure_ascii=False)
    return {'first_route': first_a['route'], 'first_path': first_a['path'],
            'first_field_comparison': fields, 'different_fields': differences,
            'only_metadata_differs': differences == ['metadata'],
            'b_second_request_reminder_visible': reminder_visible,
            'a_first_raw_sha256': _sha(first_a), 'b_first_raw_sha256': _sha(first_b),
            'b_second_raw_sha256': _sha(second_b)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--a-run', type=Path, required=True)
    parser.add_argument('--b-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = compare(args.a_run, args.b_run)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'only_metadata_differs': result['only_metadata_differs'],
                      'b_second_reminder_visible': result[
                          'b_second_request_reminder_visible']}))
    if not result['only_metadata_differs'] or not result[
            'b_second_request_reminder_visible']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
