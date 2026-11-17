"""Zero-model checks for the manager worker's final HTTP audit."""

import asyncio
import ast
import hashlib
import json
import os
from pathlib import Path
import time

import httpx

SOURCE = (Path(__file__).resolve().parents[1] /
          "method_discovery/curator_supervisor_convergence_v0/"
          "pma_full_upstream_ga_v1_20261013/worker_main.py")


def audit_hook():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"append_private_audit", "install_http_wire_audit"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(nodes) == 2
    namespace = {"httpx": httpx, "json": json, "hashlib": hashlib,
                 "time": time, "os": os, "Path": Path,
                 "PMAAuditIntegrityError": RuntimeError}
    module = ast.Module(body=[ast.ImportFrom(module="__future__",
                                              names=[ast.alias(name="annotations")], level=0),
                              *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace["install_http_wire_audit"]


def test_wire_audit_preserves_request_response_and_correlates_continuations(tmp_path):
    original_send = httpx.AsyncClient.send
    current_call = {"value": None}
    received = []
    secret = "private-credential-do-not-log"
    body = {
        "model": "claude-opus-5", "temperature": 0.2,
        "thinking": {"type": "adaptive"}, "output_config": {"effort": "high"},
        "tools": [{"name": "memory_read", "input_schema": {"type": "object"}}],
        "messages": [{"role": "user", "content": secret}],
    }

    def handler(request):
        received.append(request)
        return httpx.Response(200, json={"ok": True})

    try:
        audit_hook()(tmp_path, current_call)

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                current_call["value"] = 1
                try:
                    for _ in range(2):
                        request = httpx.Request("POST", "https://private.invalid/v1/messages",
                                                json=body, headers={"authorization": secret,
                                                                    "anthropic-version": "2023-06-01"})
                        response = await client.send(request)
                        assert response.status_code == 200
                        assert received[-1] is request
                        assert json.loads(received[-1].content) == body
                finally:
                    current_call["value"] = None
                current_call["value"] = 2
                try:
                    request = httpx.Request("POST", "https://private.invalid/v1/messages", json=body)
                    assert (await client.send(request)).status_code == 200
                finally:
                    current_call["value"] = None

        asyncio.run(run())
    finally:
        httpx.AsyncClient.send = original_send

    raw = (tmp_path / "memory_http_wire.jsonl").read_text(encoding="utf-8")
    assert secret not in raw
    assert "private.invalid" not in raw
    assert len(received) == 3
    rows = [json.loads(line) for line in raw.splitlines()]
    assert [row["request_index"] for row in rows] == [1, 2, 3]
    assert [row["call_sequence"] for row in rows] == [1, 1, 2]
    assert [row["attempt_in_call"] for row in rows] == [1, 2, 1]
    assert all(row["temperature_present"] and row["temperature"] == 0.2 for row in rows)
    assert all(row["tool_names"] == ["memory_read"] for row in rows)
    assert all(row["http_status"] == 200 for row in rows)


def test_wire_audit_records_transport_error_without_swallowing_it(tmp_path):
    original_send = httpx.AsyncClient.send

    def handler(_request):
        raise httpx.ConnectError("synthetic connection failure")

    try:
        audit_hook()(tmp_path, {"value": 4})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                try:
                    await client.post("https://private.invalid/v1/messages", json={"temperature": 0.2})
                except httpx.ConnectError:
                    return
                raise AssertionError("transport exception was swallowed")

        asyncio.run(run())
    finally:
        httpx.AsyncClient.send = original_send

    row = json.loads((tmp_path / "memory_http_wire.jsonl").read_text(encoding="utf-8"))
    assert row["call_sequence"] == 4
    assert row["transport_error_type"] == "ConnectError"
    assert row["temperature"] == 0.2
    assert "http_status" not in row
