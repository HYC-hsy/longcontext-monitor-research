"""Default-off GA-side client for the host PMA event protocol.

Only public Task events cross this path.  PMA source, bank, logs and keys stay
in the host worker.  A timed-out accepted event is never replayed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import uuid


class PMABridgeError(RuntimeError):
    pass


def append_reminder(message, reminder):
    if message.get('role') != 'user':
        raise PMABridgeError('PMA reminder requires current GA user input')
    content = message.get('content', '')
    if isinstance(content, str):
        content += '\n\n' + reminder
    elif isinstance(content, list):
        content = [*content, {'type': 'text', 'text': '\n\n' + reminder}]
    else:
        raise PMABridgeError('unsupported GA input envelope')
    return {**message, 'content': content}


class UpstreamPMAClient:
    def __init__(self, *, run_id, task_id, requests, responses, deadline):
        self.run_id, self.task_id = run_id, task_id
        self.requests = Path(requests).resolve(strict=True)
        self.responses = Path(responses).resolve(strict=True)
        self.deadline = (None if deadline == 'uncapped' else float(deadline))
        self.sequence = 0
        if not self.requests.is_dir() or not self.responses.is_dir():
            raise PMABridgeError('PMA spool unavailable')

    @classmethod
    def from_environment(cls, initial_content, *, turn_offset=0):
        if turn_offset != 0:
            raise PMABridgeError('upstream PMA supports fresh Task episodes only')
        required = ('GA_BENCH_RUN_ID', 'GA_BENCH_TASK_ID',
                    'GA_PMA_UPSTREAM_REQUESTS', 'GA_PMA_UPSTREAM_RESPONSES',
                    'GA_PMA_UPSTREAM_DEADLINE_EPOCH')
        if any(not os.environ.get(name) for name in required):
            raise PMABridgeError('PMA run identity or spool configuration absent')
        if (os.environ['GA_PMA_UPSTREAM_DEADLINE_EPOCH'] == 'uncapped' and
                os.environ.get('GA_PMA_UPSTREAM_CANDIDATE') != 'pma_gap_memory_v0'):
            raise PMABridgeError('uncapped PMA deadline requires gap candidate identity')
        client = cls(run_id=os.environ['GA_BENCH_RUN_ID'],
                     task_id=os.environ['GA_BENCH_TASK_ID'],
                     requests=os.environ['GA_PMA_UPSTREAM_REQUESTS'],
                     responses=os.environ['GA_PMA_UPSTREAM_RESPONSES'],
                     deadline=os.environ['GA_PMA_UPSTREAM_DEADLINE_EPOCH'])
        client.exchange('task_start', initial_user_content=initial_content)
        return client

    def exchange(self, kind, **fields):
        if self.deadline is not None and time.time() >= self.deadline:
            raise PMABridgeError('PMA shared deadline expired')
        self.sequence += 1
        event_id = uuid.uuid4().hex
        payload = {'schema': 'pma-ga-events-v1', 'run_id': self.run_id,
                   'task_id': self.task_id, 'event_id': event_id,
                   'sequence': self.sequence, 'kind': kind, **fields}
        request = self.requests / (event_id + '.json')
        fd, pending = tempfile.mkstemp(prefix='.pending-', dir=self.requests)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, request)
        finally:
            if os.path.exists(pending):
                os.unlink(pending)
        response = self.responses / request.name
        while not response.is_file():
            if self.deadline is not None and time.time() >= self.deadline:
                raise PMABridgeError('PMA result unknown; do not replay accepted event')
            time.sleep(.02)
        try:
            receipt = json.loads(response.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise PMABridgeError('PMA receipt unreadable') from exc
        if (receipt.get('run_id'), receipt.get('task_id'), receipt.get('event_id')) != (
                self.run_id, self.task_id, event_id):
            raise PMABridgeError('PMA receipt identity mismatch')
        if receipt.get('status') != 'ok' or not isinstance(receipt.get('result'), dict):
            raise PMABridgeError('PMA worker failed; see host-private audit')
        self.last_event_id = event_id
        return receipt['result']

    def before_actor_call(self, attempt):
        return self.exchange('before_actor_call', actor_attempt=attempt).get('reminder')

    def actor_step(self, attempt, *, status, response='', commands=(), observation='',
                   request_event_id=None):
        return self.exchange('actor_step', actor_attempt=attempt, step_status=status,
                             response=response, commands=list(commands),
                             observation=observation,
                             request_event_id=request_event_id)

    def task_end(self, terminal):
        return self.exchange('task_end', terminal=terminal)
