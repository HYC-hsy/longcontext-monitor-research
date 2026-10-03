"""Research-only first-send gate for the frozen isolated gateway.

This module is mounted in the gateway sidecar, never in the task container.
It delegates request conversion and all network/stream handling to the
unmodified isolated_transport module.  A missing host permit fails closed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import uuid


_CURRENT = threading.local()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp." + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def atomic_bytes(path: Path, value: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp." + uuid.uuid4().hex)
    temporary.write_bytes(value)
    os.replace(temporary, path)


def gate_resolver(original, control_dir: Path, slot_id: str, timeout_sec: float):
    """Call the frozen resolver once, then wait for a role-specific host permit."""
    def resolve(path, body, config, route_id=None):
        resolved = original(path, body, config, route_id)
        if resolved[3] is None:  # telemetry is not a model request
            return resolved
        if (control_dir / "closed.json").exists():
            raise ValueError("Inference is closed for this slot")
        if route_id not in (None, "monitor", resolved[3].get("model")):
            raise ValueError("Unknown inference route")
        role = "monitor" if route_id == "monitor" else "task"
        request_id = uuid.uuid4().hex
        request_hash = digest(resolved[2])
        record = {
            "slot_id": slot_id, "request_id": request_id,
            "role": role, "route_id": route_id,
            "request_sha256": request_hash,
            "request_bytes": len(resolved[2]),
            "path": path, "time_ns": time.time_ns(),
        }
        atomic_bytes(control_dir / f"{request_id}.request.json", resolved[2])
        atomic_json(control_dir / f"{request_id}.pending.json", record)
        deadline = time.monotonic() + timeout_sec
        permit_path = control_dir / f"{request_id}.permit.json"
        while time.monotonic() < deadline:
            if permit_path.exists():
                permit = json.loads(permit_path.read_text(encoding="utf-8"))
                if (permit.get("slot_id") != slot_id
                        or permit.get("request_id") != request_id
                        or permit.get("role") != role
                        or permit.get("request_sha256") != request_hash
                        or permit.get("decision") != "allow"):
                    raise ValueError("First-send permit denied or mismatched")
                _CURRENT.request_id = request_id
                return resolved
            time.sleep(0.02)
        raise TimeoutError("First-send gate timed out")
    return resolve


def install(transport, control_dir: Path, slot_id: str, timeout_sec: float) -> None:
    original = transport._resolve_request
    transport._resolve_request = gate_resolver(original, control_dir, slot_id, timeout_sec)
    emit = transport.emit_transport_event

    def audited_emit(stage, **kwargs):
        request_id = getattr(_CURRENT, "request_id", None)
        if request_id and stage in ("connected", "request_sent", "response_stream_completed"):
            atomic_json(control_dir / f"{request_id}.{stage}.json", {
                "slot_id": slot_id, "request_id": request_id,
                "stage": stage, "time_ns": time.time_ns(),
            })
        return emit(stage, **kwargs)
    transport.emit_transport_event = audited_emit
    original_send = transport.http.client.HTTPSConnection.request

    def send_if_open(connection, *args, **kwargs):
        if (control_dir / "closed.json").exists():
            raise ValueError("Inference closed before upstream send")
        request_id = getattr(_CURRENT, "request_id", None)
        if request_id:
            atomic_json(control_dir / f"{request_id}.request_begin.json", {
                "slot_id": slot_id, "request_id": request_id,
                "stage": "request_begin", "time_ns": time.time_ns(),
            })
        return original_send(connection, *args, **kwargs)

    transport.http.client.HTTPSConnection.request = send_if_open


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--control-dir", required=True)
    parser.add_argument("--slot-id", required=True)
    parser.add_argument("--timeout-sec", type=float, default=120.0)
    args = parser.parse_args()
    control_dir = Path(args.control_dir)
    if not control_dir.is_dir():
        raise RuntimeError("Missing first-send control directory")
    spec = importlib.util.spec_from_file_location("frozen_isolated_transport", args.transport)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen transport")
    transport = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(transport)
    install(transport, control_dir, args.slot_id, args.timeout_sec)
    # The frozen transport parser owns the actual gateway lifecycle.
    import sys
    sys.argv = [args.transport, "gateway", "--config", args.config]
    transport.main()


if __name__ == "__main__":
    main()
