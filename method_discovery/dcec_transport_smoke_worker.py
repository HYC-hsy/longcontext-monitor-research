"""One-call isolated transport smoke worker (not a scientific agent run)."""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from monitor_agent_core.provider import MonitorProviderClient


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def perform_smoke(config: dict, prompt: str, expected: str) -> dict:
    """Make exactly one production client complete() call with no tools."""
    if int(config.get("max_retries", -1)) != 0:
        raise ValueError("smoke provider max_retries must equal 0")
    client = MonitorProviderClient("claude_monitor_opus48", config)
    # Deliberately do not set recovery_deadline: provider recovery would create
    # a second request batch even with max_retries=0.
    progress = []
    client.progress_callback = lambda event, **fields: progress.append({"event": event, **fields})
    # Keep the manifest prompt as the only semantic instruction. No agent or
    # DCEC system contract is loaded for this infrastructure-only request.
    client.system = ""
    started = time.monotonic()
    response = None
    error = None
    try:
        response = client.complete([{"role": "user", "content": prompt}], [])
    except Exception as exc:  # Result must survive the single failed attempt.
        error = {"type": type(exc).__name__, "message": str(exc)[:500]}
    elapsed = time.monotonic() - started
    attempts = list(client.request_attempts)
    usage = list(client.usage_records)
    metadata = dict(getattr(client, "last_response_metadata", {}) or {})
    text = response.content.strip() if response is not None else ""
    result = {
        "classification": "INFRASTRUCTURE SMOKE - NOT A SCIENTIFIC RECORD",
        "status": "completed" if response is not None else "transport_error",
        "http_transport_success": response is not None,
        "logical_calls": client.complete_calls,
        "provider_attempts": len(attempts),
        "request_attempts": attempts,
        "stream_complete": bool(metadata.get("stream_complete")) if response is not None else False,
        "response_metadata": metadata,
        "usage": response.usage if response is not None else None,
        "usage_records": usage,
        "final_text": text,
        "exact_text_match": text == expected,
        "tool_calls": len(response.tool_calls) if response is not None else 0,
        "elapsed_seconds": elapsed,
        "error": error,
        "progress_events": progress,
        "dcec_enabled": False,
        "scientific_fixture_loaded": False,
    }
    if result["logical_calls"] != 1 or result["provider_attempts"] > 1:
        raise RuntimeError("smoke one-call/one-request invariant was violated")
    return result


def execute(config_path: Path, output: Path) -> dict:
    if str(os.environ.get("GA_MONITOR_DCEC", "")).strip().lower() not in {"", "0", "false", "off"}:
        raise RuntimeError("DCEC must remain disabled for infrastructure smoke")
    spec = json.loads(config_path.read_text(encoding="utf-8"))
    if spec.get("dcec_enabled") is not False or spec.get("scientific_fixture_used") is not False:
        raise ValueError("smoke config must disable DCEC and scientific fixture")
    bridge = subprocess.Popen([sys.executable, "/source/isolated_transport.py", "local"])
    try:
        # The local bridge is the only network path available in the no-network container.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", 18765)) == 0:
                    break
            time.sleep(0.05)
        else:
            raise RuntimeError("isolated local transport bridge did not become ready")
        result = perform_smoke(spec["provider_config"], spec["prompt"], spec["expected_short_response"])
    finally:
        bridge.terminate()
        try:
            bridge.wait(timeout=2)
        except subprocess.TimeoutExpired:
            bridge.kill()
            bridge.wait(timeout=2)
    _write_json(output / "result.json", result)
    print("DCEC_SMOKE " + json.dumps(result, ensure_ascii=False), flush=True)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    execute(args.config, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
