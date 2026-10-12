"""Classify one completed native ``go test -json -count=1`` receipt.

This does not run Go or assert that a test oracle is correct. The caller must
retain the unmodified process output, command and private source identity.
"""

from __future__ import annotations

import hashlib
import json


def classify_go_test(raw: bytes, *, exit_code, reason, requested_test: str | None):
    if not isinstance(raw, bytes):
        raise TypeError('Raw native Go output must be bytes')
    record = {'kind': 'go_test_native_json', 'raw_sha256': hashlib.sha256(raw).hexdigest(),
              'raw_bytes': len(raw), 'exit_code': exit_code, 'reason': reason,
              'requested_test': requested_test, 'events': 0, 'tests_run': [],
              'tests_passed': [], 'tests_failed': [], 'tests_skipped': [],
              'package_passed': False, 'package_failed': False,
              'behavior_verified': False}
    if reason in {'timeout', 'cancelled', 'cleanup_error'}:
        record['classification'] = reason
        return record
    if not raw or not raw.endswith(b'\n'):
        record['classification'] = 'output_incomplete'
        return record
    events = []
    diagnostic_prefix = []
    try:
        for line in raw.splitlines():
            if not line.startswith(b'{') and not events:
                diagnostic_prefix.append(line)
                continue
            event = json.loads(line)
            if not isinstance(event, dict) or not isinstance(event.get('Action'), str):
                raise ValueError('Non-event in native Go output')
            events.append(event)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        record['classification'] = 'output_incomplete'
        return record
    record['events'] = len(events)
    record['compiler_diagnostic_sha256'] = (hashlib.sha256(b'\n'.join(
        diagnostic_prefix)).hexdigest() if diagnostic_prefix else None)
    for event in events:
        action, test = event['Action'], event.get('Test')
        if action == 'run' and test:
            record['tests_run'].append(test)
        elif action in {'pass', 'fail', 'skip'} and test:
            record[{'pass': 'tests_passed', 'fail': 'tests_failed',
                    'skip': 'tests_skipped'}[action]].append(test)
        elif action == 'pass' and not test:
            record['package_passed'] = True
        elif action == 'fail' and not test:
            record['package_failed'] = True
    runs = set(record['tests_run'])
    passed = set(record['tests_passed'])
    failed = set(record['tests_failed'])
    skipped = set(record['tests_skipped'])
    native_build_failed = any('[build failed]' in event.get('Output', '')
                              for event in events if event.get('Action') == 'output')
    if diagnostic_prefix and not (exit_code and record['package_failed'] and native_build_failed):
        record['classification'] = 'output_incomplete'
    elif exit_code is None:
        record['classification'] = 'process_incomplete'
    elif not runs:
        record['classification'] = 'build_or_environment_failure' if exit_code else 'zero_matching_tests'
    elif failed:
        record['classification'] = 'test_failed'
    elif runs <= skipped:
        record['classification'] = 'all_skipped'
    elif exit_code != 0 or record['package_failed']:
        record['classification'] = 'package_or_environment_failure'
    elif not record['package_passed'] or not runs <= passed | skipped:
        record['classification'] = 'output_incomplete'
    elif requested_test and requested_test not in runs:
        record['classification'] = 'requested_test_not_run'
    else:
        record['classification'] = 'test_passed'
        record['behavior_verified'] = True
    return record
