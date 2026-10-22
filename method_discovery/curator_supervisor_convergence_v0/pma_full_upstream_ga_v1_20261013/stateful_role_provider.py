"""Private GA-native role transport for the stateful-memory host worker."""

import contextlib
import hashlib
import json
import os
from pathlib import Path
import sys

from .stateful_native_count import PrivateNativeCounter
from .stateful_runtime_policy import ResearchArchive, policies


def _write_event(path, row):
    with Path(path).open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


class StatefulRoleProvider:
    ROLES = frozenset({'maintenance', 'audit', 'candidate_repair',
                       'audit_correction', 'selection'})

    def __init__(self, *, profile, context_window, archive, run_id, task_id,
                 native_context_policy="required", research_capture_policy="required"):
        self.policies = policies(dict(native_context_policy=native_context_policy,
            research_capture_policy=research_capture_policy))
        self.capture = ResearchArchive(research_capture_policy)
        self.profile = dict(profile)
        self.archive = Path(archive)
        self.run_id, self.task_id = run_id, task_id
        self.counter = PrivateNativeCounter(profile=profile,
            window=context_window,
            record=lambda row: self._record('native_count.jsonl', row)) if (
                native_context_policy == 'required') else None
        self.calls = set()

    def _record(self, name, row):
        self.capture.write(_write_event, self.archive / name, row)

    def __call__(self, role, messages, call_id, max_output):
        if role not in self.ROLES or not isinstance(call_id, str) or not call_id:
            raise ValueError('stateful role identity invalid')
        if call_id in self.calls:
            raise RuntimeError('stateful role call already attempted; never resend')
        if not isinstance(max_output, int) or max_output not in (8192, 2048):
            raise ValueError('stateful role output reserve invalid')
        if role == 'selection' and max_output != 2048:
            raise ValueError('selection output reserve mismatch')
        if role != 'selection' and max_output != 8192:
            raise ValueError('precommit output reserve mismatch')
        import llmcore
        from research_runtime import research_context
        cfg = dict(self.profile, max_tokens=max_output, max_retries=0)
        session = llmcore.NativeClaudeSession(cfg)
        session.max_retries = 0
        response_timeout = (self.profile.get('total_response_timeout') or
                            self.profile.get('read_timeout', 300))
        session.total_response_timeout = max(1.0, float(response_timeout))
        session.candidate_auxiliary_integrity = True
        session.stateful_native_context_policy = self.policies["native_context_policy"]
        session.research_capture_policy = self.policies["research_capture_policy"]
        if self.counter is not None:
            session.stateful_native_preflight = self.counter
        session.research_call_type = 'stateful_' + role
        session.research_capture_payload = True
        system = '\n'.join(item['content'] for item in messages
                           if item['role'] == 'system')
        request = [{'role': item['role'], 'content': [
            {'type': 'text', 'text': item['content']}]} for item in messages
            if item['role'] != 'system']
        if not system or not request:
            raise ValueError('stateful role request lacks system or messages')
        session.system = system
        self.calls.add(call_id)
        self._record('role_calls.jsonl', {'call_id': call_id,
            'role': role, 'status': 'attempted', 'max_output_tokens': max_output,
            'messages_sha256': hashlib.sha256(json.dumps(messages,
                ensure_ascii=False, sort_keys=True).encode()).hexdigest()})
        sink = lambda row: self._record('provider_events.jsonl', row)
        with research_context({'experiment_id': 'pma-stateful-v1',
                               'condition_id': 'B', 'task_id': self.task_id,
                               'run_id': self.run_id,
                               'branch_id': 'stateful-' + role}, sink), \
                contextlib.redirect_stdout(sys.stderr):
            generator = session.raw_ask(request)
            try:
                while True:
                    next(generator)
            except StopIteration as done:
                blocks = done.value or []
        if (getattr(session, '_research_capture_failed', False) and
                self.policies['research_capture_policy'] == 'required'):
            raise RuntimeError('stateful auxiliary required capture failed')
        response = '\n'.join(block['text'] for block in blocks
                             if block.get('type') == 'text')
        if not response:
            raise RuntimeError('stateful auxiliary returned no public text')
        self._record('role_calls.jsonl', {'call_id': call_id,
            'role': role, 'status': 'returned',
            'public_response_sha256': hashlib.sha256(response.encode()).hexdigest()})
        return response

