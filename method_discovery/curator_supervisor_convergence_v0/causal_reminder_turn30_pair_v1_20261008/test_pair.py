"""Deterministic zero-model causal-pair gates."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from . import pair_harness as h
from .execution_control import ArmResult, PairController, PassiveCapture
from .live_runner import DEFAULT_AUTHORIZATION, validate_offline, require_live_authorization


class CausalPairZeroModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binding = h.checkpoint_binding()
        cls.state, cls.control, cls.treatment, cls.diff = h.build_pair_requests()
        cls.plan = h._read_json(h.HERE / "EXECUTION_PLAN.json")
        cls.clones = h._read_json(h.HERE / "CLONE_MANIFEST.json")

    def test_checkpoint_identity_full_binding(self):
        self.assertEqual(self.binding["identities"], h.EXPECTED)
        self.assertEqual(self.binding["authority_commit"], h.AUTHORITY_COMMIT)

    def test_history_compression_counter_recovered_from_bound_events(self):
        certificate = h.history_compression_counter_certificate()
        self.assertEqual(certificate["call_count_after_turn30_before_turn31"], 30)
        self.assertEqual(self.state["history_compression_call_count"], 30)
        self.assertEqual(self.plan["history_compression_call_count_at_checkpoint"], 30)

    def test_request_reconstruction_repeatable_in_one_process(self):
        for _ in range(6):
            state, control, treatment, diff = h.build_pair_requests()
            self.assertEqual(state, self.state)
            self.assertEqual(control, self.control)
            self.assertEqual(treatment, self.treatment)
            self.assertEqual(diff, self.diff)

    def test_control_is_historical_request(self):
        self.assertEqual(self.control, h._read_json(h.CHECKPOINT / "ORIGINAL_NEXT_REQUEST.json"))
        self.assertEqual(h.sha(self.control), h.EXPECTED["control_model_visible_sha256"])
        self.assertEqual(h.sha_bytes((h.CHECKPOINT / "ORIGINAL_NEXT_REQUEST.json").read_bytes()),
                         h.EXPECTED["historical_raw_request_sha256"])

    def test_treatment_only_frozen_suffix(self):
        expected = copy.deepcopy(self.control)
        expected["messages"][-1]["content"][-1]["text"] += "\n\n" + h.REMINDER
        self.assertEqual(self.treatment, expected)
        self.assertEqual(self.diff["other_differences"], 0)
        self.assertEqual(self.diff["structural_differences"], [{
            "path": ["messages", 50, "content", 1, "text"], "kind": "value"}])

    def test_reminder_exact_ascii_and_hash(self):
        self.assertEqual(h.frozen_reminder(), h.REMINDER)
        protocol = h._read_json(h.HERE / "FROZEN_PROTOCOL.json")
        self.assertEqual(protocol["reminder_injected_utf8_sha256"],
                         h.sha_bytes(h.REMINDER.encode("ascii")))
        self.assertEqual(protocol["reminder_file_final_lf_is_not_injected"], True)

    def test_message_roles_blocks_and_cache_locations_unchanged(self):
        self.assertEqual(len(self.control["messages"]), len(self.treatment["messages"]))
        self.assertEqual([m["role"] for m in self.control["messages"]],
                         [m["role"] for m in self.treatment["messages"]])
        self.assertEqual([[b["type"] for b in m["content"]] for m in self.control["messages"]],
                         [[b["type"] for b in m["content"]] for m in self.treatment["messages"]])
        markers = lambda request: [(i, j) for i, m in enumerate(request["messages"])
            for j, b in enumerate(m["content"]) if "cache_control" in b]
        self.assertEqual(markers(self.control), markers(self.treatment))
        self.assertEqual(self.control["messages"][-1]["content"][0],
                         self.treatment["messages"][-1]["content"][0])

    def test_provider_config_system_tools_metadata_equal(self):
        self.assertEqual(sorted(self.control), sorted(h.REQUEST_FIELDS))
        for key in h.REQUEST_FIELDS:
            if key != "messages":
                self.assertEqual(self.control[key], self.treatment[key], key)
        self.assertEqual(self.control["model"], "claude-opus-4-8")
        self.assertEqual(self.diff["ignored_transport_fields"], [])

    def test_pending_tool_protocol_and_runtime_clones(self):
        ids = self.state["native_tool_client_pending_tool_ids"]
        self.assertEqual(ids, [self.state["turn30_tool_result"]["tool_use_id"]])
        self.assertTrue(self.clones["initial_runtime_states_identical"])
        for arm in ("control", "treatment"):
            runtime = h._read_json(Path(self.clones["arms"][arm]["runtime_state_path"]))
            self.assertEqual(runtime, self.state)

    def test_workspace_clones_independent_and_git_backed(self):
        self.assertTrue(self.clones["workspaces_independent"])
        paths = [Path(self.clones["arms"][arm]["workspace_path"]) for arm in ("control", "treatment")]
        self.assertNotEqual(paths[0], paths[1])
        self.assertTrue(all((path / ".git" / "index").is_file() for path in paths))
        self.assertEqual([self.clones["arms"][a]["workspace_tree_sha256"] for a in ("control", "treatment")],
                         [h.EXPECTED["workspace_tree_sha256"]] * 2)

    def test_fresh_clone_destination_enforced(self):
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            h.prepare_independent_clones(h.LOCAL_PAIR_ROOT, self.state)

    def test_turn_offset_and_budget(self):
        self.assertEqual(self.state["handler_current_turn"], 30)
        self.assertEqual(self.state["next_task_turn"], 31)
        self.assertEqual(self.plan["max_additional_task_turns_per_arm"], 270)
        self.assertEqual(self.plan["total_task_turn_ceiling"], 300)
        self.assertEqual(self.plan["max_agent_seconds"], 10000)

    def test_supervisor_pma_and_researcher_control_disabled(self):
        self.assertTrue(all(self.plan["mechanisms_disabled"].values()))
        self.assertEqual(self.plan["isolation"], "no-network-unix-inference-v1")

    def test_live_send_default_fail_closed(self):
        self.assertFalse(DEFAULT_AUTHORIZATION.exists())
        with self.assertRaisesRegex(RuntimeError, "not authorized"):
            require_live_authorization()

    def test_native_evaluator_disabled_and_post_both_only(self):
        self.assertFalse(self.plan["native_evaluator_enabled_now"])
        self.assertEqual(self.plan["future_evaluator_order"],
                         "both continuations complete before either native evaluation")

    def test_passive_capture_does_not_mutate_request(self):
        request = copy.deepcopy(self.control)
        before = h.sha(request)
        with tempfile.TemporaryDirectory(prefix="causal_passive_test_") as temporary:
            capture = PassiveCapture(Path(temporary) / "capture.jsonl")
            capture.record("provider_pre_send", request)
            stored = json.loads(capture.path.read_text(encoding="utf-8"))
            self.assertEqual(stored["payload"], request)
        self.assertEqual(h.sha(request), before)

    def test_pair_order_rule(self):
        self.assertEqual(h.EXPECTED["workspace_tree_sha256"][-1], "0")
        self.assertEqual(self.plan["arm_order"], ["control", "treatment"])

    def test_invalidation_policy_frozen(self):
        policy = h._read_json(h.HERE / "INVALIDATION_POLICY.json")
        self.assertFalse(policy["auto_retry_whole_pair"])
        self.assertFalse(policy["selective_arm_rerun"])
        self.assertFalse(policy["best_of_n"])

    def test_controller_evaluator_only_after_both_and_neutral_path(self):
        events = []
        with tempfile.TemporaryDirectory(prefix="causal_controller_test_") as temporary:
            roots = {}
            for arm in ("control", "treatment"):
                roots[arm] = Path(temporary) / arm / "workspace"
                roots[arm].mkdir(parents=True)
                (roots[arm] / "source.go").write_text("package main\n", encoding="utf-8")
            def execute(arm):
                events.append("run:" + arm)
                return ArmResult(arm, "normal_completion", 32, 2, str(roots[arm]), str(roots[arm].parent))
            def evaluate(neutral_workspace):
                events.append("eval:" + Path(neutral_workspace).name)
                self.assertEqual(Path(neutral_workspace).name, "app")
                return {"reward": 0.0}
            controller = PairController()
            result = controller.run(execute, evaluate)
            self.assertEqual(events, ["run:control", "run:treatment", "eval:app", "eval:app"])
            self.assertEqual(result["status"], "continuations_complete")
            with self.assertRaisesRegex(RuntimeError, "single-use"):
                controller.run(execute, evaluate)

    def test_controller_failure_stops_pair_without_evaluator(self):
        calls = []
        def execute(arm):
            calls.append(arm)
            return ArmResult(arm, "infrastructure_failure", 30, 0, "unused", "raw", "provider")
        def evaluator(_workspace):
            self.fail("Evaluator must not run")
        result = PairController().run(execute, evaluator)
        self.assertEqual(calls, ["control"])
        self.assertEqual(result["status"], "infrastructure_invalid")
        self.assertFalse(result["native_evaluator_executed"])

    def test_future_and_hidden_information_excluded(self):
        leakage = h._read_json(h.CHECKPOINT / "LEAKAGE_AUDIT.json")
        self.assertTrue(leakage["future_information_excluded"])
        self.assertNotIn("native_result", self.treatment)

    def test_production_tracked_diff_zero(self):
        now_tree = subprocess.check_output(["git", "rev-parse", "HEAD:GenericAgent-main"],
                                           cwd=h.REPO, text=True).strip()
        authority_tree = subprocess.check_output(["git", "rev-parse",
            f"{h.AUTHORITY_COMMIT}:GenericAgent-main"], cwd=h.REPO, text=True).strip()
        self.assertEqual(now_tree, authority_tree)
        tracked_diff = subprocess.check_output(["git", "diff", "--name-only", "--",
            "GenericAgent-main"], cwd=h.REPO, text=True).strip()
        self.assertEqual(tracked_diff, "")

    def test_frozen_artifact_validator(self):
        report = validate_offline()
        self.assertEqual(report["status"], "CAUSAL_PAIR_ZERO_MODEL_READY")
        self.assertEqual(report["provider_send_count"], 0)
        self.assertEqual(report["native_evaluator_execution_count"], 0)


if __name__ == "__main__":
    unittest.main()
