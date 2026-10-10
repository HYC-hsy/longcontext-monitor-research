"""Zero-model native-boundary transport and control-path probe."""

import json
import copy
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .bootstrap import certify_cutoff
from .freeze_inputs import build_requests
from .native_runtime import run_native_slot
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.protocol import Audit
from method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.projection import HERE as SOURCE_DIR
from .bootstrap import candidate_config


def sse_event(event):
    return ("data: " + json.dumps(event, ensure_ascii=False)).encode("utf-8")


class FakeResponse:
    status_code = 200

    def __init__(self, calls, sequence):
        self.lines = [sse_event({"type": "message_start", "message": {
            "id": f"msg-{sequence}", "usage": {"input_tokens": 1}}})]
        if isinstance(calls, str):
            self.lines.extend([
                sse_event({"type": "content_block_start", "index": 0,
                           "content_block": {"type": "text", "text": ""}}),
                sse_event({"type": "content_block_delta", "index": 0,
                           "delta": {"type": "text_delta", "text": calls}}),
                sse_event({"type": "content_block_stop", "index": 0})])
            calls = []
        for index, (name, arguments) in enumerate(calls):
            self.lines.append(sse_event({"type": "content_block_start", "index": index,
                "content_block": {"type": "tool_use", "id": f"toolu_test_{sequence}_{index}",
                                  "name": name, "input": {}}}))
            raw = json.dumps(arguments, ensure_ascii=False)
            for half in (raw[:len(raw)//2], raw[len(raw)//2:]):
                self.lines.append(sse_event({"type": "content_block_delta", "index": index,
                    "delta": {"type": "input_json_delta", "partial_json": half}}))
            self.lines.append(sse_event({"type": "content_block_stop", "index": index}))
        self.lines.extend([sse_event({"type": "message_delta", "delta": {
            "stop_reason": "tool_use" if calls else "end_turn"}, "usage": {"output_tokens": 1}}),
                           sse_event({"type": "message_stop"})])

    def __enter__(self): return self
    def __exit__(self, *_): return False
    def iter_lines(self): return iter(self.lines)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    def post(self, _url, *, json, **_kwargs):
        self.payloads.append(copy.deepcopy(json))
        if not self.responses:
            raise AssertionError("Unexpected extra provider request")
        return FakeResponse(self.responses.pop(0), len(self.payloads))


class DockerObservationSession(FakeSession):
    def __init__(self):
        super().__init__([])
        self.handle = None

    def post(self, _url, *, json, **_kwargs):
        self.payloads.append(copy.deepcopy(json))
        sequence = len(self.payloads)
        if sequence == 1:
            calls = [('code_run', {"code": "print('isolated bridge')\n",
                                  "type": "python", "wait_seconds": 5})]
        elif sequence == 2:
            active = json["messages"][-1]["content"][0]["text"]
            handles = re.findall(r"obs:code:[0-9a-f]{24}", active)
            if not handles:
                raise AssertionError("Actual new code_run handle was not visible")
            self.handle = handles[-1]
            calls = [('allow_complete', {
                "release_blocking_state": "A public behavior may still be absent.",
                "grounding": "Public task", "ground_refs": ["task/original_task.txt"],
                "exclusion_reason": "The cited result is mechanically observed.",
                "observation_refs": [self.handle]})]
        elif sequence == 3:
            calls = [('intervene', {"message": "A correction based on public evidence."})]
        else:
            raise AssertionError("Unexpected model request")
        return FakeResponse(calls, sequence)


class NativeRuntimeTests(unittest.TestCase):
    def _fixture(self, root):
        fixture = root / "fixture"
        adapter.materialize("C02", fixture)
        certify_cutoff(fixture, adapter.ARCHIVE / "monitor/audit/dialogue.jsonl")
        return fixture

    def test_exact_first_request_then_crs_rer_final_release(self):
        requests, _ = build_requests()
        contrast = {"release_blocking_state": "A public behavior may still be absent.",
                    "grounding": "The original task states the behavior.",
                    "ground_refs": ["task/original_task.txt lines 121-127"],
                    "exclusion_reason": "The cited observation would differ in that state.",
                    "observation_refs": [
                        "monitor/audit/commands/9479d9d1854a44018f4c9212912848e9/output.log"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for arm in ("H", "R"):
                with self.subTest(arm=arm):
                    fixture = root / arm / "fixture"
                    fixture.parent.mkdir()
                    adapter.materialize("C02", fixture)
                    certify_cutoff(fixture, adapter.ARCHIVE / "monitor/audit/dialogue.jsonl")
                    audit = Audit(root / arm / "audit")
                    fake = FakeSession([[('allow_complete', contrast)],
                                        [('allow_complete', contrast)],
                                        [('allow_complete', contrast)]])
                    result = run_native_slot(fixture, requests[arm], candidate_config(), audit, fake)
                    self.assertEqual(result["terminal"], "final_release_eligible")
                    self.assertEqual(len(fake.payloads), 3)
                    self.assertEqual(fake.payloads[0], requests[arm])
                    self.assertIn("Root Epistemic Re-estimation", json.dumps(fake.payloads[2]))
                    events = [json.loads(line) for line in audit.path.read_text(encoding="utf-8").splitlines()]
                    self.assertEqual(sum(row.get("kind") == "provider_pre_send" for row in events), 3)
                    dialogue = (fixture / "monitor_private/audit/dialogue.jsonl").read_text(encoding="utf-8")
                    self.assertIn('"event": "crs_proposed"', dialogue)
                    self.assertIn('"event": "rhr_final_release_confirmed"', dialogue)
                    self.assertEqual(sum(row["model_cycles"] for row in result["root_subreviews"]), 3)
                    branches = list((fixture / "monitor_private/audit/rer_branches").glob("*.json"))
                    self.assertEqual(len(branches), 1)
                    parent = json.loads((fixture / "monitor_private/audit/provider_history.json").read_text(
                        encoding="utf-8"))
                    self.assertNotIn("Root Epistemic Re-estimation Frame", json.dumps(parent))

    def test_rejected_release_does_not_skip_later_observation(self):
        requests, _ = build_requests()
        invalid = {"release_blocking_state": "A state may be absent.",
                   "grounding": "Public task", "ground_refs": ["task/original_task.txt"],
                   "exclusion_reason": "Observation differs",
                   "observation_refs": ["task/public_events.jsonl#161"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('allow_complete', invalid),
                                 ('file_read', {"path": "task/original_task.txt", "count": 3})],
                                [('intervene', {"message": "A public correction."})]])
            result = run_native_slot(fixture, requests["H"], candidate_config(),
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            self.assertEqual(len(fake.payloads), 2)
            self.assertIn("tool_result", json.dumps(fake.payloads[1]))
            dialogue = (fixture / "monitor_private/audit/dialogue.jsonl").read_text(encoding="utf-8")
            self.assertIn("source exists but is not an observation result", dialogue)
            self.assertIn('"name": "file_read"', dialogue)

    def test_native_order_executes_before_control_only(self):
        requests, _ = build_requests()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('file_write', {"path": "monitor/before.md", "content": "before"}),
                                 ('intervene', {"message": "A correction."}),
                                 ('file_write', {"path": "monitor/after.md", "content": "after"})]])
            result = run_native_slot(fixture, requests["R"], candidate_config(),
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            self.assertEqual(len(fake.payloads), 1)
            self.assertTrue((fixture / "monitor_private/before.md").exists())
            self.assertFalse((fixture / "monitor_private/after.md").exists())
            dialogue = (fixture / "monitor_private/audit/dialogue.jsonl").read_text(encoding="utf-8")
            self.assertIn("not_executed", dialogue)

    def test_actual_docker_receipt_becomes_copyable_crs_handle(self):
        requests, _ = build_requests()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = DockerObservationSession()
            result = run_native_slot(fixture, requests["H"], candidate_config(),
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            self.assertEqual(len(fake.payloads), 3)
            self.assertRegex(fake.handle, r"obs:code:[0-9a-f]{24}")
            scripts = list((fixture / "monitor_private/audit/commands").glob("static-*/script_identity.json"))
            self.assertEqual(len(scripts), 1)
            self.assertTrue(json.loads(scripts[0].read_text(encoding="utf-8"))["byte_equal"])
            dialogue = (fixture / "monitor_private/audit/dialogue.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event": "crs_proposed"', dialogue)

    def test_same_response_repeat_cannot_confirm_crs(self):
        requests, _ = build_requests()
        contrast = {"release_blocking_state": "A public behavior may still be absent.",
                    "grounding": "Public task", "ground_refs": ["task/original_task.txt"],
                    "exclusion_reason": "Observed path differs.",
                    "observation_refs": ["monitor/audit/commands/9479d9d1854a44018f4c9212912848e9/output.log"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('allow_complete', contrast), ('allow_complete', contrast)],
                                [('intervene', {"message": "Public correction."})]])
            result = run_native_slot(fixture, requests["R"], candidate_config(),
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            dialogue = (fixture / "monitor_private/audit/dialogue.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event": "crs_proposed"', dialogue)
            self.assertNotIn('"event": "crs_confirmed"', dialogue)
            self.assertNotIn('"event": "rhr_entered"', dialogue)

    def test_root_wait_is_not_a_terminal_and_ceiling_does_not_release(self):
        requests, _ = build_requests()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('wait', {"after_turns": 1, "mode": "follow"})]])
            with patch("method_discovery.curator_supervisor_convergence_v0."
                       "diagnostic_boundary_bridge_v1_20261010.native_runtime.ROOT_CEILING", 1):
                result = run_native_slot(fixture, requests["H"], candidate_config(),
                                         Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "valid_capped_no_terminal")
            self.assertEqual(result["outer_model_cycles"], 1)
            self.assertEqual(result["provider_requests"], 1)
            self.assertNotIn("final_release_eligible", (root / "audit/events.jsonl").read_text())

    def test_task_book_mutation_enters_next_native_context(self):
        requests, _ = build_requests()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('file_write', {"path": "monitor/reference.md",
                                                 "content": "DURABLE_SENTINEL_NEW_BOOK"})],
                                [('intervene', {"message": "Public correction."})]])
            result = run_native_slot(fixture, requests["H"], candidate_config(),
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            self.assertIn("DURABLE_SENTINEL_NEW_BOOK", json.dumps(fake.payloads[1]))
            self.assertNotIn("DURABLE_SENTINEL_NEW_BOOK", json.dumps(fake.payloads[0]))

    def test_prior_static_session_name_is_not_a_citable_observation(self):
        requests, _ = build_requests()
        invalid = {"release_blocking_state": "A public behavior may still be absent.",
                   "grounding": "Public task", "ground_refs": ["task/original_task.txt"],
                   "exclusion_reason": "The cited result differs.",
                   "observation_refs": ["obs:code:static-13e6ace23cfd487ab1225f09c6696a74"]}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('allow_complete', invalid)],
                                [('intervene', {"message": "Public correction."})]])
            result = run_native_slot(fixture, requests["H"], candidate_config(),
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            dialogue = (fixture / "monitor_private/audit/dialogue.jsonl").read_text(encoding="utf-8")
            self.assertNotIn('"event": "crs_proposed"', dialogue)
            self.assertIn("observation_refs[0]", dialogue)

    def test_native_maintenance_request_is_purpose_scoped_and_counted(self):
        requests, _ = build_requests()
        config = candidate_config()
        config["monitor_history_char_limit"] = 274000
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('file_read', {"path": "task/original_task.txt", "count": 3})],
                                "A compact, revisable working note with public evidence locations.",
                                [('intervene', {"message": "Public correction."})]])
            result = run_native_slot(fixture, requests["H"], config,
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            self.assertEqual(result["outer_model_cycles"], 2)
            self.assertEqual(result["provider_requests"], 3)
            self.assertEqual(fake.payloads[1]["tools"], [])
            self.assertNotEqual(fake.payloads[1]["system"], fake.payloads[0]["system"])

    def test_native_continuation_format_repair_does_not_execute_tools(self):
        requests, _ = build_requests()
        config = candidate_config()
        config["monitor_history_char_limit"] = 274000
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = FakeSession([[('file_read', {"path": "task/original_task.txt", "count": 3})],
                                [('code_run', {"code": "echo should-not-run", "type": "bash"})],
                                "A concise complete continuation note with public evidence locations.",
                                [('intervene', {"message": "Public correction."})]])
            result = run_native_slot(fixture, requests["H"], config,
                                     Audit(root / "audit"), fake)
            self.assertEqual(result["terminal"], "static_root_intervention")
            self.assertEqual(result["outer_model_cycles"], 2)
            self.assertEqual(result["provider_requests"], 4)
            self.assertEqual(fake.payloads[1]["tools"], [])
            self.assertEqual(fake.payloads[2]["tools"], [])
            self.assertEqual(list((fixture / "monitor_private/audit/commands").glob(
                "static-*/script_identity.json")), [])
            audit = (root / "audit/events.jsonl").read_text(encoding="utf-8")
            self.assertIn("native_continuation_format_repair", audit)

    def test_malformed_sse_stops_before_any_tool_execution(self):
        requests, _ = build_requests()

        class BrokenSession(FakeSession):
            def post(self, _url, *, json, **_kwargs):
                self.payloads.append(copy.deepcopy(json))
                response = FakeResponse([], 1)
                response.lines = [b"data: {malformed"]
                return response

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self._fixture(root)
            fake = BrokenSession([])
            with self.assertRaises(Exception):
                run_native_slot(fixture, requests["H"], candidate_config(),
                                Audit(root / "audit"), fake)
            result = json.loads((root / "audit/result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["terminal"], "infrastructure_or_protocol_failure")
            self.assertEqual(result["provider_requests"], 1)
            self.assertEqual(result["accepted_responses"], 0)
            self.assertEqual(list((fixture / "monitor_private/audit/commands").glob(
                "static-*/script_identity.json")), [])


if __name__ == "__main__":
    unittest.main()
