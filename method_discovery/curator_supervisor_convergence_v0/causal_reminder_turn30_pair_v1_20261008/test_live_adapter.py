"""Zero-model certification of the inert, authorization-gated live adapters."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from . import continuation_adapter as core
from . import container_launcher as docker_adapter
from . import pair_harness as frozen
from .execution_control import ArmResult, PairController
from .live_runner import (DEFAULT_AUTHORIZATION, adapter_source_sha256,
                          require_live_authorization, run_authorized_pair)
from .native_evaluator_adapter import native_command, verify_native_identity
from .certify_live_adapter import FROZEN_FILES, git_show_bytes


class AdapterZeroModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.state, cls.control, cls.treatment, _ = frozen.build_pair_requests()

    def test_frozen_source_image_and_transport_identity(self):
        identity = docker_adapter.validate_frozen_execution_environment()
        self.assertEqual(identity["task_image"], core.TASK_IMAGE)
        self.assertEqual(identity["task_code_root"], "/app")
        self.assertEqual(identity["task_network_mode"], "none")

    def test_each_arm_stage_exact_request_and_runtime(self):
        with tempfile.TemporaryDirectory(prefix="causal_adapter_stage_") as temporary:
            roots = []
            for arm, request in (("control", self.control), ("treatment", self.treatment)):
                root = Path(temporary) / arm
                record = docker_adapter.prepare_arm_stage(
                    arm, root, self.state, self.control, self.treatment)
                roots.append(root)
                staged = json.loads((root / "runtime_checkpoint.json").read_text(encoding="utf-8"))
                self.assertEqual(record["expected_request_sha256"], core.canonical_sha(request))
                self.assertEqual(staged["history_compression_call_count"], 30)
                self.assertEqual(staged["handler_current_turn"], 30)
                self.assertEqual(staged["next_task_turn"], 31)
                self.assertEqual(staged["native_tool_client_pending_tool_ids"], [core.PENDING_TOOL_ID])
                self.assertEqual(staged["backend_history"], self.state["backend_history"])
                self.assertEqual(staged["history_info"], self.state["history_info"])
                self.assertEqual(staged["handler_working_state"], self.state["handler_working_state"])
                self.assertEqual(staged["turn30_tool_result"], self.state["turn30_tool_result"])
                self.assertEqual(staged["turn30_next_prompt"], request["messages"][-1]["content"][-1]["text"])
                self.assertFalse((root / "AUTHORIZATION.json").exists())
            self.assertNotEqual(roots[0], roots[1])
            self.assertNotEqual((roots[0] / "expected_request.json").read_bytes(),
                                (roots[1] / "expected_request.json").read_bytes())

    def test_production_bootstrap_once_then_exact_pass_through(self):
        class FakeClient:
            def __init__(self): self.calls = []
            def chat(self, messages, tools=None):
                self.calls.append((copy.deepcopy(messages), copy.deepcopy(tools)))
                if False: yield None
                return type("Reply", (), {"content": "ok", "tool_calls": (), "raw": "{}"})()
        base = FakeClient()
        wrapper = core.ProductionBootstrapClient(base, system_prompt="system",
            initial_user_input="original", next_prompt="frozen next",
            turn30_tool_result={"tool_use_id": core.PENDING_TOOL_ID, "content": "done"},
            tools=[{"name": "tool"}])
        def exhaust(generator):
            try:
                while True: next(generator)
            except StopIteration as end: return end.value
        exhaust(wrapper.chat([{"role": "system", "content": "system"},
                              {"role": "user", "content": "original"}], tools=[{"name": "tool"}]))
        second = [{"role": "user", "content": "production turn 32", "tool_results": []}]
        exhaust(wrapper.chat(second, tools=[{"name": "tool"}]))
        self.assertEqual(base.calls[0][0][1]["tool_results"][0]["tool_use_id"], core.PENDING_TOOL_ID)
        self.assertEqual(base.calls[0][0][1]["content"], "frozen next")
        self.assertEqual(base.calls[1], (second, [{"name": "tool"}]))
        self.assertEqual((wrapper.bootstrap_calls, wrapper.pass_through_calls,
                          wrapper.accepted_responses), (1, 1, 2))

    def test_first_send_same_payload_and_mismatch_pre_network(self):
        seen = []
        def original(_session, _url, _headers, payload, _parse_fn):
            seen.append(payload)
            if False: yield None
            return []
        def exhaust(generator):
            try:
                while True: next(generator)
            except StopIteration: pass
        expected = copy.deepcopy(self.control)
        guard = core.FirstSendGuard(expected, original, lambda *_: None)
        exhaust(guard(None, "local", {}, expected, None))
        self.assertIs(seen[0], expected)
        self.assertEqual(guard.first_canonical_sha, frozen.EXPECTED["control_model_visible_sha256"])
        seen.clear()
        mismatch = copy.deepcopy(expected)
        mismatch["messages"][-1]["content"][-1]["text"] += "changed"
        guard = core.FirstSendGuard(expected, original, lambda *_: None)
        with self.assertRaisesRegex(RuntimeError, "before network send"):
            next(guard(None, "local", {}, mismatch, None))
        self.assertEqual(seen, [])

    def test_container_specs_independent_networkless_task_processes(self):
        with tempfile.TemporaryDirectory(prefix="causal_compose_test_") as temporary:
            root = Path(temporary)
            for arm in ("control", "treatment"):
                for name in ("workspace", "stage", "raw"):
                    (root / arm / name).mkdir(parents=True, exist_ok=True)
            left = docker_adapter.compose_spec(root / "control/workspace",
                root / "control/stage", root / "control/raw",
                docker_adapter.FROZEN_BUNDLE / "source", project="causal-turn30-control-test")
            right = docker_adapter.compose_spec(root / "treatment/workspace",
                root / "treatment/stage", root / "treatment/raw",
                docker_adapter.FROZEN_BUNDLE / "source", project="causal-turn30-treatment-test")
            for spec in (left, right):
                main = spec["services"]["main"]
                self.assertEqual(main["image"], core.TASK_IMAGE)
                self.assertEqual(main["network_mode"], "none")
                self.assertEqual(main["working_dir"], "/app")
                self.assertIn("/tests", main["tmpfs"])
                self.assertEqual(main["environment"]["GA_PMA_ENABLED"], "0")
                self.assertEqual(main["environment"]["GA_MONITOR_ENABLED"], "0")
                self.assertEqual(main["entrypoint"][-1], "--authorized-child")
            self.assertNotEqual(left["services"]["main"]["volumes"],
                                right["services"]["main"]["volumes"])
            config_file = root / "compose.json"
            config_file.write_text(json.dumps(left), encoding="utf-8")
            checked = subprocess.run(["docker", "compose", "-p", "causal-turn30-configtest",
                                      "-f", str(config_file), "config", "--quiet"],
                                     capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_native_evaluator_is_post_both_and_label_neutral(self):
        verify_native_identity()
        with tempfile.TemporaryDirectory(prefix="causal_native_cmd_") as temporary:
            neutral = Path(temporary) / "app"
            neutral.mkdir()
            out = Path(temporary) / "result"
            out.mkdir()
            cmd = native_command(neutral, out)
            joined = " ".join(cmd).lower()
            self.assertIn("/tests/test.sh", joined)
            self.assertNotIn("treatment", joined)
            self.assertNotIn("control", joined)
            self.assertNotIn("reminder", joined)
            self.assertIn("--network none", joined)
        calls = []
        def arm(name):
            calls.append("arm:" + name)
            return ArmResult(name, "normal_completion", 31, 1, ".", ".")
        def evaluator(_path):
            calls.append("evaluator")
            return {}
        with tempfile.TemporaryDirectory(prefix="causal_native_controller_") as temporary:
            workspace = Path(temporary)
            def actual_arm(name):
                calls.append("arm:" + name)
                return ArmResult(name, "normal_completion", 31, 1, str(workspace), str(workspace))
            PairController().run(actual_arm, evaluator)
        self.assertEqual(calls, ["arm:control", "arm:treatment", "evaluator", "evaluator"])

    def test_live_authorization_missing_and_production_unchanged(self):
        self.assertFalse(DEFAULT_AUTHORIZATION.exists())
        template = json.loads((frozen.HERE / "AUTHORIZATION_TEMPLATE.json").read_text(encoding="utf-8"))
        self.assertIs(template["execution_authorized"], False)
        self.assertEqual(template["live_adapter_source_sha256"], adapter_source_sha256())
        with self.assertRaisesRegex(RuntimeError, "not authorized"):
            require_live_authorization()
        def forbidden(_arg):
            self.fail("No Task or evaluator adapter may run without authorization")
        with self.assertRaisesRegex(RuntimeError, "not authorized"):
            run_authorized_pair(authorization=DEFAULT_AUTHORIZATION,
                                execute_arm=forbidden, evaluate_workspace=forbidden)
        tree = subprocess.check_output(["git", "rev-parse", "HEAD:GenericAgent-main"],
                                       cwd=frozen.REPO, text=True).strip()
        original = subprocess.check_output(["git", "rev-parse",
            f"{frozen.AUTHORITY_COMMIT}:GenericAgent-main"], cwd=frozen.REPO, text=True).strip()
        self.assertEqual(tree, original)
        self.assertEqual(subprocess.check_output(["git", "diff", "--name-only", "--",
            "GenericAgent-main"], cwd=frozen.REPO, text=True).strip(), "")

    def test_frozen_causal_protocol_artifacts_byte_identical(self):
        for name in FROZEN_FILES:
            path = frozen.HERE / name
            self.assertEqual(path.read_bytes(), git_show_bytes(
                "e784da69bb604a130c8d02a85a35d47c9a0de362", path), name)

    def test_partial_child_failure_accounting_is_mechanical(self):
        with tempfile.TemporaryDirectory(prefix="causal_partial_counts_") as temporary:
            path = Path(temporary) / "events.jsonl"
            rows = [
                {"kind": "task_turn", "payload": {"turn": 31}},
                {"kind": "production_chat_result", "payload": {"content": "accepted", "raw": "{}"}},
                {"kind": "task_turn", "payload": {"turn": 32}},
                {"kind": "production_chat_result", "payload": {"content": "!!!Error: transport", "raw": "{}"}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n{", encoding="utf-8")
            self.assertEqual(docker_adapter.partial_task_counts(path), (1, 32))

    def test_real_image_zero_model_request_builder_both_arms(self):
        # Two fresh task-image processes. No gateway is mounted, and the
        # production transport is intercepted before any socket/provider send.
        with tempfile.TemporaryDirectory(prefix="causal_image_cert_") as temporary:
            root = Path(temporary)
            for arm, expected in (("control", self.control), ("treatment", self.treatment)):
                stage = root / arm
                docker_adapter.prepare_arm_stage(arm, stage, self.state,
                                                 self.control, self.treatment)
                source_workspace = Path(frozen._read_json(frozen.HERE / "CLONE_MANIFEST.json")
                    ["arms"][arm]["workspace_path"])
                workspace = root / (arm + "_workspace")
                shutil.copytree(source_workspace, workspace)
                source_copy = root / (arm + "_production_source")
                shutil.copytree(docker_adapter.FROZEN_BUNDLE / "source", source_copy,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "temp"))
                command = docker_adapter.zero_model_container_command(
                    workspace, stage, source_copy)
                result = subprocess.run(command, capture_output=True, text=True,
                                        timeout=180, check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                lines = [line for line in result.stdout.splitlines() if line.startswith("{")]
                report = json.loads(lines[-1])
                self.assertEqual(report["request_sha256"], core.canonical_sha(expected))
                self.assertEqual(report["network_send_count"], 0)
                self.assertEqual(report["task_agent_loop_run_count"], 0)
                self.assertEqual(report["production_handler"], "ga.GenericAgentHandler")
                self.assertEqual(report["production_loop"], "agent_loop.agent_runner_loop")
                self.assertEqual(report["checkpoint_identity"]["compression_counter"], 30)


if __name__ == "__main__":
    unittest.main()
