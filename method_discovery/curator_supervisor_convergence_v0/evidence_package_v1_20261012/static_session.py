"""Host-owned, fake-transport-only static diagnostic entry.

No live mode is exposed here. The Task is a certified, immutable cutoff tree;
controls are archived as proposals and never delivered to a Task process.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading
import time

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.analysis_spool import SpoolAnalysisSessions
from monitor_agent_core.provider import MonitorProviderClient

from .static_host import prepare_static


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


class StaticDiagnosticSession:
    """One fresh process should own one instance and one immutable cutoff."""

    def __init__(self, scene: str, destination: Path, *, condition: str, fake_post):
        if condition not in {'N', 'evidence_package_v1'} or not callable(fake_post):
            raise ValueError('Static session requires a named condition and fake transport')
        self.manifest, self.port, self.bridge = prepare_static(scene, destination)
        self.stop = threading.Event()
        self.errors = []
        config = {'apikey': 'offline-test-only', 'apibase': 'https://offline.invalid',
                  'provider': 'anthropic', 'model': 'claude-opus-4-8',
                  'max_retries': 0, 'monitor_adaptive_supervisory_environment': True,
                  'monitor_narrow_supervisor_v1': True,
                  'monitor_evidence_package_v1': condition == 'evidence_package_v1',
                  'monitor_contrastive_release_state': False,
                  'monitor_receding_horizon_release': False,
                  'monitor_root_epistemic_reestimation': False,
                  'monitor_history_projection': 'off'}
        self.client = MonitorProviderClient('offline-static', config)
        self.client.transport_post = fake_post
        self.monitor = MonitorAgent(self.client, self.port.workspace,
                                    max_review_turns=20, stop_event=self.stop)
        self.monitor.analysis = SpoolAnalysisSessions(self.bridge.root, self.bridge.run_id,
                                                       self.stop, response_timeout=90)
        self.monitor.intervention_callback = None
        self.monitor.task_budget_state = lambda: (83 if scene == 'C02' else 0, 300)
        self.capture_root = Path(destination) / 'host_requests'
        self.capture_root.mkdir()
        self.request_count = 0

        def capture(request_id, payload):
            if self.stop.is_set():
                raise RuntimeError('Static session stopped before provider send')
            if self.monitor.evidence_package_v1:
                self.monitor._evidence_pre_send(payload)
            if not isinstance(request_id, str) or not request_id or '/' in request_id:
                raise RuntimeError('Invalid static request identity')
            self.request_count += 1
            raw = _canonical(payload)
            path = self.capture_root / (f'{self.request_count:04d}-{request_id}.json')
            if path.exists():
                raise RuntimeError('Static request archive would be overwritten')
            path.write_bytes(raw)
            if path.read_bytes() != raw:
                raise RuntimeError('Static request archive readback mismatch')
            (self.capture_root / (path.name + '.sha256')).write_text(
                hashlib.sha256(raw).hexdigest() + '\n', encoding='ascii')

        self.client.pre_send_capture = capture
        self.thread = threading.Thread(target=self._serve, name='static-host-spool', daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            while not self.stop.is_set() and not self.bridge.closed:
                self.bridge.serve_once()
                time.sleep(.02)
        except Exception as exc:
            self.errors.append(exc)
            self.stop.set()

    def review(self, wake_context: str, *, root_handoff=None, max_turns=20):
        if self.stop.is_set() or self.errors:
            raise RuntimeError('Static host spool unavailable')
        if root_handoff is not None:
            frozen = dict(root_handoff)
            self.monitor.completion_state = lambda: dict(frozen)
        action = self.monitor.review(wake_context, completion_pending=root_handoff is not None,
                                     root_handoff=root_handoff, max_turns_override=max_turns)
        if self.errors:
            raise RuntimeError('Static host spool failed during review') from self.errors[0]
        record = {'kind': action.kind, 'payload': action.payload,
                  'simulated': True, 'input_sent': False, 'task_process_started': False}
        path = self.capture_root.parent / 'STATIC_CONTROL_PROPOSAL.json'
        path.write_bytes(_canonical(record))
        return record

    def close(self):
        self.stop.set()
        failures = []
        try:
            self.monitor.analysis.close()
        except Exception as exc:
            failures.append(exc)
        self.thread.join(timeout=15)
        if self.thread.is_alive():
            failures.append(RuntimeError('Static spool thread did not stop'))
        if not self.bridge.closed:
            try:
                self.bridge.close()
            except Exception as exc:
                failures.append(exc)
        failures.extend(self.errors)
        if failures:
            raise RuntimeError('Static session cleanup uncertain') from failures[0]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
