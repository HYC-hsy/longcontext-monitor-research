"""No-network protocol fixtures; one chain uses the real certified Docker tool port."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from .adapter import materialize, request
from .docker_tool import DockerToolPort
from .protocol import (Audit, RUN_BUDGET, StaticBudgetExhausted, StaticClient,
                       StaticProtocolError, ordinary_tools, run_static)


def config():
    return {"apikey": "offline-test-only", "apibase": "http://127.0.0.1:1",
            "provider": "anthropic", "model": "claude-opus-4-8", "max_tokens": 8192,
            "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
            "context_win": 200000, "max_retries": 0}


def sse_tool(tool_id="toolu_static_1", name="wait", argument='{"after_turns":1}',
             *, split=False, complete=True):
    events = [
        {"type": "message_start", "message": {"id": "msg_static", "usage": {"input_tokens": 1}}},
        {"type": "content_block_start", "content_block": {"type": "thinking"}},
        {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "consider"}},
        {"type": "content_block_delta", "delta": {"type": "signature_delta", "signature": "sig-static"}},
        {"type": "content_block_stop"},
        {"type": "content_block_start", "content_block": {"type": "tool_use", "id": tool_id,
                                                  "name": name}},
    ]
    fragments = [argument[:len(argument)//2], argument[len(argument)//2:]] if split else [argument]
    events.extend({"type": "content_block_delta", "delta": {"type": "input_json_delta",
                                                            "partial_json": piece}} for piece in fragments)
    events.extend([{"type": "content_block_stop"},
                   {"type": "message_delta", "delta": {"stop_reason": "tool_use"},
                    "usage": {"output_tokens": 2}}])
    if complete:
        events.append({"type": "message_stop"})
    return [("data: " + json.dumps(event)).encode() for event in events]


def sse_many(calls):
    combined = []
    for index, (tool_id, name, argument) in enumerate(calls):
        section = sse_tool(tool_id, name, argument)
        combined.extend(section if index == 0 else section[1:])
        if index < len(calls) - 1:
            combined = combined[:-2]
    return combined


class FakeResponse:
    status_code = 200
    def __init__(self, lines): self.lines = lines
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def iter_lines(self): yield from self.lines


class FakeTransport:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []
    def __call__(self, _url, **kwargs):
        self.requests.append(copy.deepcopy(kwargs["json"]))
        return FakeResponse(next(self.responses))


class ProtocolTests(unittest.TestCase):
    def test_full_stream_tool_result_next_request_and_terminal(self):
        with tempfile.TemporaryDirectory(prefix="static-protocol-") as temp:
            root = Path(temp)
            fixture = root / "fixture"
            materialize("C01", fixture)
            first = sse_tool(name="code_run", argument=json.dumps({
                "code": "print('static probe')", "type": "python", "timeout": 10,
                "wait_seconds": 5}), split=True)
            second = sse_tool("toolu_static_2", "wait", '{"after_turns":1}')
            transport = FakeTransport([first, second])
            audit = Audit(root / "audit")
            result = run_static("C01", "B", config(), fixture, audit, transport)
            self.assertEqual(result["terminal"], "wait_proposal")
            self.assertEqual(result["provider_requests"], 2)
            self.assertEqual(result["tool_calls"], 2)
            self.assertEqual(transport.requests[0], request("C01", "B"))
            self.assertNotIn("temperature", transport.requests[0])
            self.assertEqual(len(transport.requests[1]["messages"]),
                             len(transport.requests[0]["messages"]) + 2)
            assistant = transport.requests[1]["messages"][-2]
            self.assertEqual(assistant["content"][0]["signature"], "sig-static")
            self.assertEqual(assistant["content"][1]["input"]["code"], "print('static probe')")
            user = transport.requests[1]["messages"][-1]
            receipt = next(x for x in user["content"] if x["type"] == "tool_result")
            self.assertEqual(receipt["tool_use_id"], "toolu_static_1")
            self.assertIn("static probe", (fixture / "monitor_private/audit/commands" /
                                            json.loads(receipt["content"])["session_id"] /
                                            "output.log").read_text())
            self.assertIn(json.loads(receipt["content"])["status"], {"running", "success"})
            self.assertEqual(len(list((root / "audit").glob("stream_*.sse"))), 2)

    def test_incomplete_stream_and_json_never_execute_tool(self):
        for lines in (sse_tool(complete=False), sse_tool(argument='{"after_turns":')):
            with self.subTest(lines=len(lines)), tempfile.TemporaryDirectory() as temp:
                frozen = request("C01", "B")
                transport = FakeTransport([lines])
                client = StaticClient(config(), frozen, Audit(Path(temp) / "audit"), transport)
                with self.assertRaises(Exception):
                    client.complete([{"role": "system", "content": frozen["system"]}],
                                    ordinary_tools(frozen))
                self.assertEqual(client.accepted_responses, 0)
                self.assertEqual(len(transport.requests), 1)

    def test_conflicting_or_duplicate_controls_are_rejected(self):
        lines = sse_tool()[:-1] + sse_tool("toolu_static_2", "intervene",
                                          '{"message":"second"}')[5:]
        with tempfile.TemporaryDirectory() as temp:
            frozen = request("C01", "B")
            client = StaticClient(config(), frozen, Audit(Path(temp) / "audit"), FakeTransport([lines]))
            with self.assertRaises(StaticProtocolError):
                client.complete([{"role": "system", "content": frozen["system"]}],
                                ordinary_tools(frozen))

    def test_first_send_mismatch_fails_before_transport(self):
        with tempfile.TemporaryDirectory() as temp:
            frozen = request("C01", "B")
            transport = FakeTransport([sse_tool()])
            client = StaticClient(config(), frozen, Audit(Path(temp) / "audit"), transport)
            client.system += "changed"
            with self.assertRaises(StaticProtocolError):
                client._request_once(ordinary_tools(frozen))
            self.assertEqual(transport.requests, [])

    def test_invalid_tool_args_are_not_executed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            materialize("C01", fixture)
            transport = FakeTransport([sse_tool(name="file_read", argument='{"path":9}'),
                                       sse_tool("toolu_static_2", "wait")])
            result = run_static("C01", "B", config(), fixture, Audit(root / "audit"), transport)
            self.assertEqual(result["terminal"], "wait_proposal")
            receipt = transport.requests[1]["messages"][-1]["content"][0]
            self.assertEqual(json.loads(receipt["content"])["status"], "error")

    def test_duplicate_response_id_cannot_repeat_tool(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            materialize("C01", fixture)
            repeated = sse_tool(name="file_read", argument='{"path":"task/original_task.txt"}')
            result = run_static("C01", "B", config(), fixture, Audit(root / "audit"),
                                FakeTransport([repeated, repeated]))
            self.assertEqual(result["terminal"], "protocol_or_infrastructure_failure")
            self.assertEqual(result["tool_calls"], 1)

    def test_tool_failure_is_returned_not_promoted_to_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            materialize("C01", fixture)
            transport = FakeTransport([sse_tool(name="file_read", argument='{"path":"monitor/no-such-file"}'),
                                       sse_tool("toolu_static_2", "wait")])
            result = run_static("C01", "B", config(), fixture, Audit(root / "audit"), transport)
            self.assertEqual(result["terminal"], "wait_proposal")
            receipt = next(b for b in transport.requests[1]["messages"][-1]["content"]
                           if b["type"] == "tool_result")
            self.assertEqual(json.loads(receipt["content"])["status"], "execution_unconfirmed")

    def test_mixed_response_executes_only_through_first_control(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            materialize("C01", fixture)
            calls = [("toolu_read", "file_read", '{"path":"task/original_task.txt"}'),
                     ("toolu_wait", "wait", '{"after_turns":1}'),
                     ("toolu_later", "file_write", '{"path":"monitor/later.txt","content":"bad"}')]
            transport = FakeTransport([sse_many(calls)])
            result = run_static("C01", "B", config(), fixture, Audit(root / "audit"), transport)
            self.assertEqual(result["terminal"], "wait_proposal")
            self.assertEqual(result["tool_calls"], 2)
            self.assertFalse((fixture / "monitor_private/later.txt").exists())
            self.assertEqual(len(transport.requests), 1)
            events = (root / "audit/events.jsonl").read_text(encoding="utf-8")
            self.assertIn("not_executed", events)

    def test_valid_control_suppresses_every_cooccurring_tool_before_side_effects(self):
        variants = [
            [("toolu_write", "file_write", '{"path":"monitor/marker.txt","content":"side-effect"}'),
             ("toolu_wait", "wait", '{"after_turns":1}')],
            [("toolu_wait", "wait", '{"after_turns":1}'),
             ("toolu_write", "file_write", '{"path":"monitor/marker.txt","content":"side-effect"}')],
            [("toolu_first", "file_write", '{"path":"monitor/marker.txt","content":"side-effect"}'),
             ("toolu_wait", "wait", '{"after_turns":1}'),
             ("toolu_last", "file_write", '{"path":"monitor/second.txt","content":"side-effect"}')],
        ]
        for calls in variants:
            with self.subTest(names=[item[1] for item in calls]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture = root / "fixture"
                materialize("C01", fixture)
                transport = FakeTransport([sse_many(calls)])
                result = run_static("C01", "B", config(), fixture, Audit(root / "audit"), transport)
                self.assertEqual(result["terminal"], "wait_proposal")
                self.assertEqual(result["provider_requests"], 1)
                self.assertEqual(result["proposed_tool_calls"], len(calls))
                self.assertEqual(result["not_executed"], len(calls) - 1)
                self.assertEqual(result["ordinary_port_calls"], 0)
                self.assertFalse((fixture / "monitor_private/marker.txt").exists())
                self.assertFalse((fixture / "monitor_private/second.txt").exists())
                events = (root / "audit/events.jsonl").read_text(encoding="utf-8")
                self.assertIn("response_control_preflight", events)
                self.assertIn("not_executed", events)

    def test_invalid_control_does_not_suppress_ordinary_tools_or_next_request(self):
        variants = [
            [("toolu_bad", "wait", '{"after_turns":"bad"}')],
            [("toolu_bad", "wait", '{"after_turns":"bad"}'),
             ("toolu_write", "file_write", '{"path":"monitor/marker.txt","content":"observed"}')],
        ]
        for calls in variants:
            with self.subTest(mixed=len(calls) > 1), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture = root / "fixture"
                materialize("C01", fixture)
                transport = FakeTransport([sse_many(calls),
                                           sse_tool("toolu_final", "wait", '{"after_turns":1}')])
                result = run_static("C01", "B", config(), fixture, Audit(root / "audit"), transport)
                self.assertEqual(result["terminal"], "wait_proposal")
                self.assertEqual(result["provider_requests"], 2)
                self.assertEqual(result["parameter_rejections"], 1)
                self.assertEqual((fixture / "monitor_private/marker.txt").exists(), len(calls) > 1)
                results = {block["tool_use_id"]: json.loads(block["content"])
                           for block in transport.requests[1]["messages"][-1]["content"]
                           if block["type"] == "tool_result"}
                self.assertEqual(results["toolu_bad"]["status"], "error")
                if len(calls) > 1:
                    self.assertNotEqual(results["toolu_write"].get("status"), "error")
                    self.assertEqual((fixture / "monitor_private/marker.txt").read_text(
                        encoding="utf-8"), "observed")

    def test_duplicate_ids_and_conflicting_controls_reject_before_any_side_effect(self):
        variants = [
            [("toolu_same", "file_write", '{"path":"monitor/marker.txt","content":"bad"}'),
             ("toolu_same", "wait", '{"after_turns":1}')],
            [("toolu_write", "file_write", '{"path":"monitor/marker.txt","content":"bad"}'),
             ("toolu_wait", "wait", '{"after_turns":1}'),
             ("toolu_intervene", "intervene", '{"message":"x"}')],
        ]
        for calls in variants:
            with self.subTest(names=[item[1] for item in calls]), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture = root / "fixture"
                materialize("C01", fixture)
                result = run_static("C01", "B", config(), fixture, Audit(root / "audit"),
                                    FakeTransport([sse_many(calls)]))
                self.assertEqual(result["terminal"], "protocol_or_infrastructure_failure")
                self.assertEqual(result["tool_calls"], 0)
                self.assertFalse((fixture / "monitor_private/marker.txt").exists())

    def test_script_byte_mismatch_is_adapter_failure_not_model_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture = root / "fixture"
            materialize("C01", fixture)
            transport = FakeTransport([sse_tool(name="code_run", argument=json.dumps({
                "type": "bash", "code": "printf ok", "wait_seconds": 1}))])
            def corrupt(path, raw):
                path.write_bytes(raw + b"\r")
            with mock.patch.object(DockerToolPort, "_persist_script", staticmethod(corrupt)):
                result = run_static("C01", "B", config(), fixture, Audit(root / "audit"), transport)
            self.assertEqual(result["terminal"], "protocol_or_infrastructure_failure")
            self.assertEqual(result["provider_requests"], 1)
            self.assertIn("adapter_integrity_failure",
                          (root / "audit/events.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(len(list((fixture / "monitor_private/audit/commands").glob("static-*/output.log"))), 0)

    def test_300_turn_host_ceiling_is_not_a_12_request_or_tool_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            frozen = request("C01", "B")
            transport = FakeTransport([sse_tool()])
            client = StaticClient(config(), frozen, Audit(Path(temp) / "audit"), transport)
            self.assertEqual(RUN_BUDGET["model_turns_per_diagnostic"], 300)
            self.assertIsNone(RUN_BUDGET["total_tool_call_cap"])
            self.assertIsNone(RUN_BUDGET["total_tool_wait_cap"])
            client.outer_cycles = 301
            with self.assertRaises(StaticBudgetExhausted):
                client._request_once(ordinary_tools(frozen))
            self.assertEqual(transport.requests, [])
