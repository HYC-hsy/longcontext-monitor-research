"""One runtime-owned selected public check; no semantic verifier or task repair."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time
import uuid


GUIDANCE = """Keep one ongoing understanding and working note across ordinary and root decisions. A substantive correction remains open until actual Task feedback and a selected public check, if one is needed, are considered. Select at most one executable check with code_run verification metadata; ordinary navigation needs no such metadata. Task owns implementation and task tests; your selected check observes and must not edit the implementation. A queued check is not a result. Its exit status and output support only the stated scope, and a changed input, timeout or failed check is not a pass. At a root handoff, consider unresolved local feedback before judging the whole task. Explicitly resolve, revise, withdraw or defer the current follow-up; local support does not establish whole-task completion. Use the seven ordinary tools, public requirements and actual artifacts; do not treat hidden evaluation as online evidence."""


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


class SelectedVerification:
    def __init__(self, workspace, analysis, audit, due_turn=None):
        self.workspace = workspace
        self.analysis = analysis
        self.audit = audit
        self.due_turn = due_turn
        self.current = None
        self.receipt = None
        self.follow_pending = False
        self.follow_message = None
        self.version = 0
        self.running = False
        self.last_run_turn = None

    def _inputs(self, paths):
        result = {}
        for path in paths:
            if not isinstance(path, str) or not path.startswith('task/workspace/'):
                raise ValueError('verification artifacts must be task/workspace/ paths')
            try:
                source = self.workspace.resolve_read(path)
                result[path] = ({'status': 'file', 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
                                if source.is_file() else {'status': 'unavailable'})
            except OSError as exc:
                result[path] = {'status': 'unavailable', 'error_type': type(exc).__name__}
        return result

    def register(self, arguments, task_turn):
        metadata = arguments.get('verification')
        if not isinstance(metadata, dict):
            raise ValueError('verification metadata must be an object')
        scope = metadata.get('scope')
        basis = str(metadata.get('basis') or '').strip()
        question = str(metadata.get('question') or '').strip()
        paths = metadata.get('artifacts')
        if scope not in {'local', 'root'} or not basis or not question or not isinstance(paths, list) or not paths:
            raise ValueError('verification needs scope, public basis, question and artifacts')
        if len(paths) > 8 or len(set(paths)) != len(paths):
            raise ValueError('verification artifacts must be 1-8 distinct paths')
        if not isinstance(arguments.get('code'), str) or not arguments['code'].strip():
            raise ValueError('selected verification needs executable code')
        if len(arguments['code']) > 12000 or len(basis) > 2000 or len(question) > 2000:
            raise ValueError('selected verification definition is too large')
        if arguments.get('type', 'python') not in {'python', 'bash', 'powershell'}:
            raise ValueError('unsupported verification command type')
        if not isinstance(arguments.get('timeout', 60), int) or not 0 < arguments.get('timeout', 60) <= 300:
            raise ValueError('verification timeout must be 1-300 seconds')
        if (self.current and self.current['scope'] == 'local' and scope == 'root'
                and not self.current.get('resolved')):
            if metadata.get('prior_disposition') not in {'withdraw', 'revise'} or not str(metadata.get('prior_reason') or '').strip():
                raise ValueError('Resolve or explicitly revise/withdraw the local follow-up before root selection')
            self.audit('verification_prior_revised', disposition=metadata['prior_disposition'],
                       reason=metadata['prior_reason'], prior_id=self.current['id'])
            self.follow_pending = False
        definition = {key: arguments.get(key) for key in ('code', 'type', 'timeout')}
        definition.update(scope=scope, basis=basis, question=question, artifacts=paths)
        digest = _sha(definition)
        if self.current and self.current['definition_sha256'] == digest:
            return {'status': 'already_selected', 'verification_id': self.current['id'],
                    'version': self.current['version'], 'receipt': self.receipt}
        inputs = self._inputs(paths)
        self.version += 1
        self.current = dict(definition, id=uuid.uuid4().hex, version=self.version,
                            definition_sha256=digest, inputs=inputs, selected_turn=task_turn,
                            resolved=False)
        self.receipt = None
        self.last_run_turn = None
        if self.due_turn is not None:
            self.due_turn.value = -1  # wait(follow) arms the natural Task boundary
        self.audit('verification_selected', definition=self.current)
        return {'status': 'queued', 'verification_id': self.current['id'],
                'version': self.version, 'definition_sha256': digest,
                'task_workspace': str(self.workspace.task_mounts['workspace']),
                'note': 'Selected only; no execution result yet.'}

    def arm_follow(self, task_turn, after_turns):
        if self.current is None or self.due_turn is None:
            return
        due = task_turn + max(1, int(after_turns))
        if self.last_run_turn is not None:
            due = max(due, self.last_run_turn + 5)
        self.due_turn.value = due
        self.audit('verification_follow_armed', verification_id=self.current['id'],
                   from_turn=task_turn, due_turn=due)

    def on_intervention(self, message):
        self.follow_pending = True
        self.follow_message = message
        self.audit('verification_follow_opened', message=message)

    def run_due(self, task_turn, *, force=False):
        current = self.current
        if current is None or self.running:
            return {'status': 'not_selected' if current is None else 'already_running'}
        inputs = self._inputs(current['artifacts'])
        if (self.receipt and not self.receipt.get('input_changed_during_check')
                and inputs == self.receipt.get('inputs_after')):
            if self.due_turn is not None and not force:
                self.due_turn.value = -1
            return {'status': 'reused', 'verification_id': current['id'], 'receipt': self.receipt}
        if not force and self.last_run_turn is not None and task_turn - self.last_run_turn < 5:
            if self.due_turn is not None:
                self.due_turn.value = self.last_run_turn + 5
            return {'status': 'cooldown', 'verification_id': current['id']}
        self.running = True
        try:
            started = time.time()
            try:
                session = self.analysis.start(current['code'], current.get('type') or 'python',
                                              current.get('timeout') or 60, wait_seconds=0)
                entry = self.analysis.sessions[session['session_id']]
                entry['done'].wait((current.get('timeout') or 60) + 3)
                observed = self.analysis.read(session['session_id'], wait_seconds=0)
                full_output = entry['output'].read_bytes()
                observed['output_excerpt'] = full_output[:12000].decode('utf-8', errors='replace')
                observed['output_excerpt_truncated'] = len(full_output) > 12000
                observed.pop('stdout', None)  # one bounded copy; full bytes stay in output_path
            except Exception as exc:
                session = None
                observed = {'status': 'error', 'reason': type(exc).__name__, 'stdout': ''}
            after = self._inputs(current['artifacts'])
            receipt = {'verification_id': current['id'], 'version': current['version'],
                       'definition_sha256': current['definition_sha256'],
                       'task_turn': task_turn, 'started_at': started, 'finished_at': time.time(),
                       'command': current['code'], 'type': current.get('type') or 'python',
                       'session_id': session['session_id'] if session else None, 'result': observed,
                       'inputs_before': inputs, 'inputs_after': after,
                       'input_changed_during_check': inputs != after}
            self.receipt = receipt
            self.last_run_turn = task_turn
            if self.due_turn is not None:
                self.due_turn.value = -1  # next ordinary retest is armed by a later follow choice
            self.audit('verification_result', receipt=receipt)
            return {'status': 'observed', 'verification_id': current['id'], 'receipt': receipt}
        finally:
            self.running = False

    def dispose(self, result, reason, *, root=False):
        if result not in {'resolve', 'withdraw', 'revise', 'defer'} or not str(reason or '').strip():
            raise ValueError('result and a reason are required')
        if result == 'resolve':
            receipt = self.receipt
            if not self.current or not receipt or receipt['verification_id'] != self.current['id']:
                raise ValueError('No current verification receipt supports resolve')
            if receipt['result']['status'] != 'success' or receipt['input_changed_during_check']:
                raise ValueError('A failed, running, changed or unavailable check cannot resolve')
            if any(item.get('status') != 'file' for item in receipt['inputs_after'].values()):
                raise ValueError('A selected input is unavailable; the result is not stable support')
            if self._inputs(self.current['artifacts']) != receipt['inputs_after']:
                raise ValueError('Selected inputs changed after the check; requalify the current result')
            if root and self.current['scope'] != 'root':
                raise ValueError('Local verification does not resolve the root scope')
        self.audit('verification_disposition', result=result, reason=reason,
                   verification_id=self.current['id'] if self.current else None)
        if result == 'resolve' and self.current is not None:
            self.current['resolved'] = True
        if result in {'resolve', 'withdraw', 'revise'}:
            self.follow_pending = False
        if result in {'withdraw', 'revise'}:
            self.current = None
            self.receipt = None
            if self.due_turn is not None:
                self.due_turn.value = -1

    def context(self):
        if not self.follow_pending and self.current is None:
            return None
        data = {'follow_pending': self.follow_pending,
                'follow_message': self.follow_message,
                'selected': self.current,
                'receipt': self.receipt,
                'status': 'not_selected' if self.current is None else
                          'no_result_yet' if self.receipt is None else self.receipt['result']['status']}
        return 'Current public verification and follow-up (runtime observations, not a verdict):\n' + json.dumps(
            data, ensure_ascii=False, default=str)
