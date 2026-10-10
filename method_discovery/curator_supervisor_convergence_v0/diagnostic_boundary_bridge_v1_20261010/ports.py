"""Per-slot isolated analysis and no-op Task control ports."""

from __future__ import annotations

import subprocess
import uuid

from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.docker_tool import StaticIntegrityError
from .payload_client import BridgeIntegrityError


class IsolatedAnalysis:
    def __init__(self, docker_port, audit):
        self.port = docker_port
        self.audit = audit
        self.integrity_error = None

    def _execute(self, arguments):
        try:
            result = self.port.execute("code_run", arguments)
            self.audit.record("isolated_analysis_result", arguments=arguments, result=result)
            return result
        except StaticIntegrityError as exc:
            self.integrity_error = exc
            self.audit.record("adapter_integrity_failure", error_type=type(exc).__name__)
            raise

    def start(self, code, kind, timeout, wait_seconds):
        return self._execute({"code": code, "type": kind, "timeout": timeout,
                              "wait_seconds": wait_seconds})

    def read(self, session_id, wait_seconds, cancel):
        return self._execute({"session_id": session_id, "wait_seconds": wait_seconds,
                              "cancel": cancel})

    def close(self):
        first_error = None
        try:
            self.port.close()
        except Exception as exc:
            first_error = exc
        for name, entry in self.port.new_sessions.items():
            if entry["process"].poll() is None or entry.get("reason") == "cleanup_error":
                first_error = first_error or BridgeIntegrityError(
                    f"Analysis process cleanup unconfirmed: {name}")
            inspected = subprocess.run(["docker", "container", "inspect", name],
                                       capture_output=True, timeout=15, check=False)
            if inspected.returncode != 1:
                first_error = first_error or BridgeIntegrityError(
                    f"Analysis container removal unconfirmed: {name}; inspect={inspected.returncode}")
        if first_error is not None:
            raise BridgeIntegrityError("Per-slot analysis cleanup unconfirmed") from first_error
        self.audit.record("isolated_analysis_cleanup_confirmed",
                          sessions=list(self.port.new_sessions))


class NoTaskControl:
    def __init__(self, audit, handoff):
        self.audit = audit
        self.handoff = dict(handoff)
        self.interventions = []

    def submit_intervention(self, message):
        receipt = {"submission_id": "static-" + uuid.uuid4().hex,
                   "submitted_task_turn": 83, "submitted_cursor": 161,
                   "executed": False, "delivered": False,
                   "delivery_status": "no_op_static_task_not_running"}
        self.interventions.append({"message": message, "receipt": receipt})
        self.audit.record("static_intervention_noop", message=message,
                          handoff=self.handoff, receipt=receipt)
        return receipt

    def final_release(self, action, current_handoff):
        if (action.kind != "allow_complete" or
                action.payload.get("request_id") != self.handoff["request_id"] or
                action.payload.get("root_frame_generation") != self.handoff["generation"] or
                current_handoff != self.handoff):
            raise BridgeIntegrityError("Stale root release at the simulated Task port")
        self.audit.record("final_release_eligible", handoff=self.handoff,
                          executed=False, delivered=False)
