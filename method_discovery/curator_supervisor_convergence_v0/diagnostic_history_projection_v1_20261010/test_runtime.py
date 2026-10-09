import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from .projection import project
from .run_batch import ORDER, child, direct_session, requests
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.adapter import materialize
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.protocol import Audit, StaticClient, StaticProtocolError, ordinary_tools, run_static
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.test_protocol import FakeTransport, config, sse_tool


class RuntimeTests(unittest.TestCase):
    def test_direct_transport_ignores_system_proxy_without_disabling_tls_validation(self):
        with direct_session() as session:
            self.assertFalse(session.trust_env)
            settings = session.merge_environment_settings(
                "https://example.invalid", {}, None, None, None)
            self.assertEqual(settings["proxies"], {})
            self.assertTrue(settings["verify"])

    def test_child_passes_direct_session_to_certified_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            freeze = root / "freeze.json"
            freeze.write_text("{}", encoding="utf-8")
            seen = []
            def fake_run(_scene, _arm, _profile, _fixture, _audit, *, transport, frozen_request):
                seen.append((transport.__self__.trust_env, frozen_request))
                return {"terminal": "wait_proposal", "provider_requests": 1}
            with mock.patch("method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.run_batch.validate_freeze", return_value={}), \
                 mock.patch("method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.run_batch.adapter.materialize", return_value={"workspace_tree_sha256": "fixture", "visible_files": []}), \
                 mock.patch("method_discovery.curator_supervisor_convergence_v0.diagnostic_history_projection_v1_20261010.run_batch.run_static", side_effect=fake_run):
                child(root / "slot", "R", freeze)
            self.assertEqual(seen, [(False, requests()["R"])])

    def test_two_frozen_requests_and_tail(self):
        h, r, _ = project()
        self.assertEqual(requests(), {"H": h, "R": r})
        self.assertEqual(h["messages"][88:], r["messages"][1:])
        self.assertEqual([list(pair) for pair in ORDER],
                         [[1,"H","R"],[2,"R","H"],[3,"H","R"],
                          [4,"R","H"],[5,"H","R"],[6,"R","H"]])

    def test_real_loop_fake_transport_for_both_conditions(self):
        for arm, frozen in requests().items():
            with self.subTest(arm=arm), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                fixture = root / "fixture"
                materialize("C02", fixture)
                transport = FakeTransport([
                    sse_tool("toolu_projection_read_1", "file_read",
                             '{"path":"task/original_task.txt"}', split=True),
                    sse_tool("toolu_projection_wait_2", "wait", '{"after_turns":1}')])
                result = run_static("C02", arm, config(), fixture, Audit(root / "audit"),
                                    transport, frozen_request=frozen)
                self.assertEqual(result["terminal"], "wait_proposal")
                self.assertEqual(result["provider_requests"], 2)
                self.assertEqual(transport.requests[0], frozen)
                self.assertEqual(transport.requests[1]["messages"][:len(frozen["messages"])],
                                 frozen["messages"])
                self.assertEqual({k:v for k,v in transport.requests[1].items() if k != "messages"},
                                 {k:v for k,v in frozen.items() if k != "messages"})
                assistant, response = transport.requests[1]["messages"][-2:]
                self.assertEqual(assistant["content"][1]["id"], "toolu_projection_read_1")
                result_block = next(b for b in response["content"] if b["type"] == "tool_result")
                self.assertEqual(result_block["tool_use_id"], "toolu_projection_read_1")
                self.assertIn("original", json.loads(result_block["content"])["path"])

    def test_r_first_send_gate_rejects_drift_before_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            frozen = requests()["R"]
            transport = FakeTransport([sse_tool()])
            client = StaticClient(config(), frozen, Audit(Path(tmp) / "audit"), transport)
            client.system += " altered"
            with self.assertRaises(StaticProtocolError):
                client._request_once(ordinary_tools(frozen))
            self.assertEqual(transport.requests, [])

    def test_condition_runs_do_not_share_payload_objects(self):
        first = requests()
        second = requests()
        first["R"]["messages"][0]["content"][0]["text"] += "mutation"
        self.assertEqual(second, requests())
        self.assertNotEqual(first["R"], second["R"])


if __name__ == "__main__":
    unittest.main()
