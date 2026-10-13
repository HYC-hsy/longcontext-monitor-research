"""One-use synthetic Task/PMA endpoint compatibility check, not a pilot arm."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')

STAGE = Path(__file__).resolve().parent
REPO = STAGE.parents[2]


def _append(path: Path, value: dict) -> None:
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                default=str) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_check(root: Path, profile_path: Path) -> dict:
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    import llmcore
    source = runpy.run_path(str(profile_path))['native_claude_cc_vibe_opus48']
    if (source.get('model'), source.get('max_tokens'), source.get('temperature'),
            source.get('thinking_type')) != ('claude-opus-4-8', 64000, 1, 'adaptive'):
        raise RuntimeError('Task synthetic check configuration differs from frozen pilot')
    session = llmcore.NativeClaudeSession(dict(source))
    session.system = 'Synthetic transport compatibility check. Give a brief reply.'
    session.tools = [{'name': 'compat_noop', 'description': 'Do not use in this check.',
                      'input_schema': {'type': 'object', 'properties': {}}}]
    original_post = llmcore.requests.post
    attempts = []

    class ObservedResponse:
        def __init__(self, raw, number):
            self.raw, self.number = raw, number

        def __enter__(self):
            self.raw.__enter__()
            _append(root / 'task_transport.jsonl', {
                'attempt': self.number, 'event': 'response_headers',
                'status_code': self.raw.status_code, 'time': time.time()})
            return self

        def __exit__(self, *args):
            return self.raw.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self.raw, name)

        def iter_lines(self, *args, **kwargs):
            for line in self.raw.iter_lines(*args, **kwargs):
                _append(root / 'task_sse.jsonl', {'attempt': self.number,
                                                  'line': line.decode('utf-8') if
                                                  isinstance(line, bytes) else line})
                yield line

    def observed_post(url, **kwargs):
        number = len(attempts) + 1
        attempts.append(number)
        _append(root / 'task_transport.jsonl', {
            'attempt': number, 'event': 'request_attempt', 'time': time.time(),
            'payload': kwargs.get('json'), 'timeout': kwargs.get('timeout'),
            'verify': kwargs.get('verify')})
        return ObservedResponse(original_post(url, **kwargs), number)

    llmcore.requests.post = observed_post
    try:
        generator = session.raw_ask([{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Synthetic check only: reply briefly; do not call tools.'}]}])
        try:
            while True:
                next(generator)
        except StopIteration as done:
            blocks = done.value
    finally:
        llmcore.requests.post = original_post
    if not isinstance(blocks, list) or not blocks or any(
            block.get('type') == 'tool_use' for block in blocks):
        raise RuntimeError('Task compatibility response is incomplete or proposed a tool')
    if any('!!!Error' in str(block) or '流异常中断' in str(block) for block in blocks):
        raise RuntimeError('Task compatibility returned a provider error')
    lines = [json.loads(line)['line'] for line in (root / 'task_sse.jsonl').read_text(
        encoding='utf-8').splitlines()]
    if not any('"type":"message_stop"' in line.replace(' ', '') for line in lines):
        raise RuntimeError('Task compatibility response lacks message_stop')
    returned_models = []
    for line in lines:
        if not line.startswith('data:') or line[5:].strip() == '[DONE]':
            continue
        event = json.loads(line[5:].strip())
        if event.get('type') == 'message_start':
            returned_models.append(event.get('message', {}).get('model'))
    (root / 'task_response.json').write_text(json.dumps({
        'blocks': blocks, 'actual_attempts': len(attempts),
        'returned_model': returned_models[-1] if returned_models else None},
        ensure_ascii=False, indent=2), encoding='utf-8')
    return {'logical_requests': 1, 'actual_attempts': len(attempts),
            'complete': True, 'model_requested': source['model'],
            'model_returned': returned_models[-1] if returned_models else None}


async def _pma_check(root: Path, profile_path: Path) -> dict:
    sys.path.insert(0, str(STAGE / 'vendor/pma_89e5c0d/external/harbor/src'))
    sys.path.insert(0, str(STAGE / 'vendor/pma_89e5c0d/src'))
    sys.path.insert(0, str(STAGE))
    import litellm
    from episode import PMAEpisode, construct_upstream
    from worker_main import install_transport_audit
    profile = json.loads(profile_path.read_text(encoding='utf-8'))['claude_monitor_opus48']
    agent = construct_upstream(root / 'upstream_agent', memory_profile=profile)
    episode = PMAEpisode(agent, run_id='synthetic-compat', task_id='synthetic',
                         archive=root / 'pma_private')
    install_transport_audit(agent, episode.archive)
    original = litellm.acompletion
    attempts = []
    phase_errors = []

    class ErrorCapture(logging.Handler):
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                phase_errors.append({'logger': record.name, 'message': record.getMessage()})

    capture = ErrorCapture()
    loggers = [logging.getLogger('memory_agent.memory.memory_agent'),
               logging.getLogger('memory_agent.memory_enabled_agent')]
    for logger in loggers:
        logger.addHandler(capture)

    async def observed_completion(**kwargs):
        number = len(attempts) + 1
        attempts.append(number)
        visible = {key: value for key, value in kwargs.items() if key not in (
            'api_base', 'api_key', 'logger_fn')}
        _append(root / 'pma_transport.jsonl', {'attempt': number,
            'event': 'request_attempt', 'time': time.time(), 'kwargs': visible,
            'api_base_present': bool(kwargs.get('api_base')),
            'api_key_present': bool(kwargs.get('api_key'))})
        try:
            response = await original(**kwargs)
            _append(root / 'pma_transport.jsonl', {'attempt': number,
                'event': 'response', 'time': time.time(),
                'response': response.model_dump() if hasattr(response, 'model_dump')
                else str(response)})
            return response
        except BaseException as exc:
            _append(root / 'pma_transport.jsonl', {'attempt': number,
                'event': 'failure', 'time': time.time(), 'type': type(exc).__name__})
            raise

    litellm.acompletion = observed_completion
    try:
        event = {'kind': 'task_start', 'sequence': 1, 'event_id': 'synthetic-start',
                 'run_id': 'synthetic-compat', 'task_id': 'synthetic',
                 'initial_user_content': 'Synthetic public memory check. No benchmark task.'}
        result = await episode.handle(event)
    finally:
        litellm.acompletion = original
        for logger in loggers:
            logger.removeHandler(capture)
    rows = [json.loads(line) for line in (episode.archive / 'memory_transport.jsonl').read_text(
        encoding='utf-8').splitlines()]
    if (result.get('triggered') is not True or len(rows) != 2 or
            any(row.get('status') != 'complete' for row in rows) or
            len(attempts) < 2 or phase_errors):
        (root / 'pma_phase_errors.json').write_text(json.dumps(phase_errors), encoding='utf-8')
        raise RuntimeError('PMA two-phase compatibility was not complete')
    return {'logical_phases': 2, 'actual_attempts': len(attempts),
            'complete': True, 'model_requested': profile['model'],
            'reminder_selected': bool(agent._pending_injection)}


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ('run-root', 'task-profile-file', 'pma-profile-file',
                 'audited-code-commit'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--execute-once', action='store_true')
    args = parser.parse_args()
    if not args.execute_once:
        raise RuntimeError('synthetic compatibility network check requires --execute-once')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout.strip()
    if head != args.audited_code_commit:
        raise RuntimeError('synthetic compatibility code identity differs')
    root = Path(args.run_root).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    record = {'schema': 'pma-ga-synthetic-compat-v1', 'code_commit': head,
              'task_profile_sha256': _sha(Path(args.task_profile_file)),
              'pma_profile_sha256': _sha(Path(args.pma_profile_file)),
              'task': None, 'pma': None, 'failures': []}
    try:
        try:
            record['task'] = _task_check(root, Path(args.task_profile_file))
        except BaseException as exc:
            record['failures'].append({'component': 'task', 'type': type(exc).__name__,
                                       'message': str(exc)})
        try:
            record['pma'] = asyncio.run(_pma_check(root, Path(args.pma_profile_file)))
        except BaseException as exc:
            record['failures'].append({'component': 'pma', 'type': type(exc).__name__,
                                       'message': str(exc)})
    finally:
        (root / 'result.json').write_text(json.dumps(record, ensure_ascii=False,
                                                     indent=2), encoding='utf-8')
    print(json.dumps({'task': record['task'], 'pma': record['pma'],
                      'failures': record['failures']}, ensure_ascii=False))
    if record['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
