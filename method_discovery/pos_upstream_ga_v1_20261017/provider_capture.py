"""Post-stop accounting for the separate PoS worker's native provider ledger."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _read_rows(path: Path):
    raw = path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('unterminated JSONL record')
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines() if line]
    if not all(isinstance(row, dict) for row in rows):
        raise ValueError('non-object event')
    return rows, {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def inspect_provider_capture(directory: Path, run_id: str, task_id: str,
                             *, profile_mode: bool) -> dict:
    """Report missing/partial data as unknown; never infer an HTTP call from a role.

    Called only after registered writers stop. This is an archive judgment, not
    permission to evaluate the safely frozen Task product.
    """
    base = Path(directory)
    role_path = base / 'events.jsonl'
    provider_path = base / 'events.provider.jsonl'
    result = {'mode': 'profile' if profile_mode else 'fake',
              'provider_file': provider_path.name,
              'role_file': role_path.name,
              'role_calls': None, 'observable_attempts': None,
              'observable_returns': None, 'capture_complete': False,
              'provider_source': None, 'role_source': None}
    if not profile_mode:
        result.update(status='fake_no_native_provider_file',
                      capture_complete=not provider_path.exists())
        return result
    try:
        roles, result['role_source'] = _read_rows(role_path)
    except (OSError, UnicodeError, ValueError, TypeError):
        result['status'] = 'role_ledger_unavailable'
        return result
    requests = [row for row in roles if row.get('event') == 'pos_role_request']
    responses = [row for row in roles if row.get('event') == 'pos_role_response']
    result['role_calls'] = len(requests)
    if not provider_path.exists():
        result['status'] = ('no_role_calls' if not requests else
                            'provider_file_missing_or_pre_send_failure')
        if not requests:
            result.update(observable_attempts=0, observable_returns=0,
                          capture_complete=True)
        return result
    try:
        events, result['provider_source'] = _read_rows(provider_path)
    except (OSError, UnicodeError, ValueError, TypeError):
        result['status'] = 'provider_ledger_unreadable'
        return result
    if any(row.get('run_id') != run_id or row.get('task_id') != task_id or
           row.get('condition_id') != 'P' or
           row.get('branch_id') not in {'pos-role-belief',
                'pos-role-consistency', 'pos-role-progress'} for row in events):
        result['status'] = 'provider_identity_mismatch'
        return result
    groups = {}
    for row in events:
        if not isinstance(row.get('llm_call_id'), str):
            result['status'] = 'provider_call_identity_missing'
            return result
        groups.setdefault(row['llm_call_id'], []).append(row)
    attempts = [row for row in events if row.get('event_type') ==
                'provider_request_attempt']
    returns = [row for row in events if row.get('event_type') ==
               'provider_response']
    result['observable_attempts'] = len(attempts)
    result['observable_returns'] = len(returns)
    ready_roles = []
    for group in groups.values():
        names = [row.get('event_type') for row in group]
        if (names.count('provider_request_ready') != 1 or
                names.count('provider_request_attempt') != 1 or
                names.count('provider_response') != 1 or
                names.index('provider_request_ready') >
                    names.index('provider_request_attempt') or
                names.index('provider_request_attempt') >
                    names.index('provider_response')):
            result['status'] = 'provider_attempt_or_return_incomplete'
            return result
        response = next(row for row in group if row.get('event_type') ==
                        'provider_response')
        if (response.get('payload') or {}).get('outcome') == 'success' and (
                names.count('provider_response_content') != 1 or
                names.index('provider_response_content') >
                    names.index('provider_response')):
            result['status'] = 'provider_visible_return_incomplete'
            return result
        ready_roles.append(group[0]['branch_id'].removeprefix('pos-role-'))
    role_names = [row.get('role') for row in requests]
    if ready_roles != role_names or len(responses) > len(returns):
        result['status'] = 'role_provider_call_mismatch'
        return result
    result.update(status='complete', capture_complete=True)
    return result
