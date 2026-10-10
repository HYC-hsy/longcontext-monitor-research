"""Pilot-only, fixed-run analysis port client; no local process fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import time
import uuid


class AnalysisPortIntegrityError(RuntimeError):
    pass


class SpoolAnalysisSessions:
    def __init__(self, root, run_id, stop_event, *, response_timeout=20):
        self.root = Path(root).resolve(strict=True)
        self.run_id = str(run_id)
        self.stop_event = stop_event
        self.response_timeout = response_timeout
        if not self.run_id or not (self.root / 'identity.json').is_file():
            raise AnalysisPortIntegrityError('Pilot analysis port identity unavailable')
        identity = json.loads((self.root / 'identity.json').read_text(encoding='utf-8'))
        if identity != {'run_id': self.run_id, 'schema': 'pilot-analysis-spool-v1'}:
            raise AnalysisPortIntegrityError('Pilot analysis port identity mismatch')
        for name in ('requests', 'responses'):
            if not (self.root / name).is_dir():
                raise AnalysisPortIntegrityError('Pilot analysis port queue missing')

    def _exchange(self, operation, **fields):
        if self.stop_event.is_set():
            raise AnalysisPortIntegrityError('Monitor stopped before analysis request')
        request_id = uuid.uuid4().hex
        request = {'schema': 'pilot-analysis-spool-v1', 'run_id': self.run_id,
                   'request_id': request_id, 'operation': operation, **fields}
        path = self.root / 'requests' / (request_id + '.json')
        descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                json.dump(request, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        response = self.root / 'responses' / (request_id + '.json')
        deadline = time.monotonic() + self.response_timeout
        while not response.is_file():
            if self.stop_event.is_set() or time.monotonic() >= deadline:
                # The host may have accepted the request. Never replay it.
                raise AnalysisPortIntegrityError('Analysis response unknown; request was not retried')
            time.sleep(.02)
        try:
            receipt = json.loads(response.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise AnalysisPortIntegrityError('Analysis receipt unreadable') from exc
        if (receipt.get('run_id'), receipt.get('request_id')) != (self.run_id, request_id):
            raise AnalysisPortIntegrityError('Analysis receipt identity mismatch')
        if receipt.get('status') != 'ok' or not isinstance(receipt.get('result'), dict):
            raise AnalysisPortIntegrityError('Analysis host did not return a complete result')
        return receipt['result']

    def start(self, code, code_type='python', timeout=60, wait_seconds=1):
        if not isinstance(code, str) or not code.strip() or code_type not in {'python', 'bash'}:
            raise ValueError('Invalid analysis script or type')
        if type(timeout) not in (int, float) or not 0 < timeout <= 300:
            raise ValueError('timeout must be in (0, 300] seconds')
        if type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 5:
            raise ValueError('wait_seconds must be between 0 and 5')
        return self._exchange('start', code=code, code_type=code_type,
                              timeout=timeout, wait_seconds=wait_seconds)

    def read(self, session_id, wait_seconds=1, cancel=False):
        if not isinstance(session_id, str) or not session_id:
            raise ValueError('session_id is required')
        if type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 5 or type(cancel) is not bool:
            raise ValueError('Invalid analysis poll arguments')
        return self._exchange('read', session_id=session_id,
                              wait_seconds=wait_seconds, cancel=cancel)

    def close(self):
        if not self.stop_event.is_set():
            self._exchange('close')
