"""Reconstruct one archived initialization count projection without generation.

The archived store is opened read-only, cloned, and replayed only in a temp
store. A probe is optional, single-attempt, and requires a matching archived
projection hash. Raw payload and exception text stay in host-private files.
"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from method_discovery.pma_stateful_memory_v1_20261021.engine import CycleEngine
from method_discovery.pma_stateful_memory_v1_20261021.source import digest
from method_discovery.pma_stateful_memory_v1_20261021.store import MemoryStore

from .stateful_memory_worker import load_bound_profile
from .stateful_native_count import (PrivateNativeCounter, _canonical,
                                    count_projection)


class _Captured(Exception):
    pass


def reconstruct(db_path: Path, profile: dict, expected_messages: str) -> dict:
    import llmcore

    with tempfile.TemporaryDirectory(prefix='stateful-count-replay-') as scratch:
        clone = Path(scratch) / 'memory.sqlite3'
        uri = 'file:' + db_path.resolve(strict=True).as_posix() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True)) as original, \
                closing(sqlite3.connect(clone)) as target:
            original.backup(target)
        store = MemoryStore(clone)
        captured = []
        try:
            # Remove only the failed-cycle journal in the disposable clone.
            store.db.execute('DELETE FROM journal')
            store.db.commit()
            task_text = store.sources()['initial-task']['text']

            def role_capture(role, messages, call_id, max_output):
                captured.append((role, messages, call_id, max_output))
                raise _Captured()

            CycleEngine(store, role_capture, task_text=task_text).run('initial')
            if len(captured) != 1:
                raise RuntimeError('archived initialization did not reconstruct once')
            role, messages, _call_id, max_output = captured[0]
            if role != 'maintenance' or max_output != 8192 or digest(messages) != expected_messages:
                raise RuntimeError('archived maintenance message hash differs')
        finally:
            store.close()

    cfg = dict(profile, max_tokens=max_output, max_retries=0)
    session = llmcore.NativeClaudeSession(cfg)
    session.max_retries = 0
    session.candidate_auxiliary_integrity = True
    session.system = '\n'.join(item['content'] for item in messages
                               if item['role'] == 'system')
    request = [{'role': item['role'], 'content': [
        {'type': 'text', 'text': item['content']}]} for item in messages
        if item['role'] != 'system']
    payloads = []

    def capture_payload(payload):
        payloads.append(payload)
        raise _Captured()

    session.stateful_native_preflight = capture_payload
    before = {name: os.environ.get(name) for name in (
        'GA_STATEFUL_MEMORY_ENABLED', 'GA_STATEFUL_MEMORY_MODE')}
    os.environ['GA_STATEFUL_MEMORY_ENABLED'] = '1'
    os.environ['GA_STATEFUL_MEMORY_MODE'] = 'live'
    try:
        generator = session.raw_ask(request)
        try:
            while True:
                next(generator)
        except _Captured:
            pass
    finally:
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    if len(payloads) != 1:
        raise RuntimeError('final native payload not captured exactly once')
    return payloads[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-db', type=Path, required=True)
    parser.add_argument('--profile-file', required=True)
    parser.add_argument('--profile-name', required=True)
    parser.add_argument('--profile-sha256', required=True)
    parser.add_argument('--messages-sha256', required=True)
    parser.add_argument('--projection-sha256', required=True)
    parser.add_argument('--private-log', type=Path)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    profile = load_bound_profile(args.profile_file, args.profile_sha256,
                                 args.profile_name)
    payload = reconstruct(args.source_db, profile, args.messages_sha256)
    projection = count_projection(payload)
    actual = hashlib.sha256(_canonical(projection)).hexdigest()
    if actual != args.projection_sha256:
        raise RuntimeError('archived count projection hash differs')
    print(json.dumps({'projection_sha256': actual,
        'projection_utf8_bytes': len(_canonical(projection)),
        'model': projection['model'], 'archived_projection_match': True,
        'generation_http_attempts': 0, 'probe_requested': args.probe}))
    if not args.probe:
        return
    if args.private_log is None or args.private_log.exists():
        raise RuntimeError('fresh host-private probe log required')
    args.private_log.parent.mkdir(parents=True, exist_ok=True)

    def record(row):
        with args.private_log.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
            stream.flush()
            os.fsync(stream.fileno())

    try:
        result = PrivateNativeCounter(profile=profile, window=1_000_000,
                                      record=record)(payload)
    except Exception as error:
        print(json.dumps({'probe': 'failed', 'error_type': type(error).__name__,
                          'private_log': str(args.private_log)}))
        raise SystemExit(2) from None
    print(json.dumps({'probe': 'accepted',
                      'native_input_tokens': result['native_input_tokens'],
                      'elapsed_seconds': result['elapsed_seconds'],
                      'context_window_tokens': result['context_window_tokens'],
                      'http_status': result['http_status']}))


if __name__ == '__main__':
    main()
