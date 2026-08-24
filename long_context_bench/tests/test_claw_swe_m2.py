import importlib.util
import sys
import unittest
import json
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_claw_swe_m2.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_claw_swe_m2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class M2AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.version_info < (3, 10) or importlib.util.find_spec("datasets") is None:
            raise unittest.SkipTest("M2 tests require the E-drive Python 3.12 host environment")
        cls.m = load_module()
        cls.identity = {
            "model": "resolved-model",
            "effective_llm_no": 2,
            "requested_llm_no": 2,
        }

    def test_fixed_candidate_is_from_registered_pool(self):
        registry = (SCRIPT.parents[1] / "tasks" / "candidates_v1.jsonl").read_text(encoding="utf-8")
        self.assertIn(f'"task_id": "{self.m.INSTANCE_ID}"', registry)

    def test_runner_requires_utf8_mode(self):
        with self.assertRaisesRegex(RuntimeError, "-X utf8"):
            self.m.require_utf8_mode(0)
        self.m.require_utf8_mode(1)

    def test_exec_command_is_unattended_and_traced(self):
        adapter = self.m.M2GenericAgentAdapter("m2-test", self.identity)
        with patch.object(self.m, "_python_home", return_value=Path("cpython-3.12.12-linux-x86_64-gnu")):
            cmd = adapter.build_exec_command("agent", "container", self.m.INSTANCE_ID)
        joined = " ".join(cmd)
        self.assertIn("--no-user-tools", cmd)
        self.assertIn("--nobg", cmd)
        self.assertIn("GA_OTEL_ENABLED=1", cmd)
        self.assertIn("GA_BENCH_RUN_ID=m2-test", cmd)
        self.assertIn("GA_BENCH_TASK_ID=" + self.m.INSTANCE_ID, cmd)
        self.assertNotIn("patch", joined.lower())
        self.assertNotIn("solution", joined.lower())

    def test_model_and_llm_number_come_from_same_resolved_identity(self):
        adapter = self.m.M2GenericAgentAdapter("m2-test", self.identity)
        self.assertEqual(adapter.model, "resolved-model")
        self.assertEqual(adapter.llm_no, 2)

    def test_m0_settings_are_explicitly_forwarded_to_task_container(self):
        env = {
            "GA_MAX_TURNS": "500",
            "GA_M0_MONITOR_ENABLED": "1",
            "GA_M0_MONITOR_CONFIG": "native_oai_cc_vibe_gpt55_xhigh",
            "GA_M0_MAX_INSPECTIONS": "12",
        }
        with patch.dict("os.environ", env, clear=False):
            adapter = self.m.M2GenericAgentAdapter("m2-test", self.identity)
            with patch.object(self.m, "_python_home", return_value=Path("cpython-3.12.12-linux-x86_64-gnu")):
                cmd = adapter.build_exec_command("agent", "container", self.m.INSTANCE_ID)
        self.assertEqual(adapter.max_turns, 500)
        self.assertIn("GA_M0_MONITOR_ENABLED=1", cmd)
        self.assertIn("GA_M0_MONITOR_CONFIG=native_oai_cc_vibe_gpt55_xhigh", cmd)
        self.assertIn("GA_M0_MAX_INSPECTIONS=12", cmd)
        self.assertIn("GA_M0_MONITOR_ARTIFACT_DIR=/opt/m2-artifacts/m0_monitor", cmd)

    def test_method_run_requires_an_exact_explicit_current_ga_hash(self):
        current = "a" * 64
        with patch.object(self.m, "_ga_source_hash", return_value=current), \
             patch.dict("os.environ", {"GA_METHOD_EXPECTED_SOURCE_SHA256": current}):
            identity = self.m.validate_ga_source()
        self.assertEqual(identity["source_contract"], "explicit_method_experiment")
        self.assertEqual(identity["expected_source_sha256"], current)

    def test_method_run_rejects_a_stale_explicit_ga_hash(self):
        with patch.object(self.m, "_ga_source_hash", return_value="a" * 64), \
             patch.dict("os.environ", {"GA_METHOD_EXPECTED_SOURCE_SHA256": "b" * 64}):
            with self.assertRaisesRegex(RuntimeError, "source mismatch"):
                self.m.validate_ga_source()

    def test_official_eval_reuses_swebench_namespace(self):
        cmd = self.m.build_eval_command("run")
        self.assertIn("swebench.harness.run_evaluation", cmd)
        self.assertEqual(cmd[cmd.index("-n") + 1], "swebench")
        self.assertEqual(cmd[cmd.index("-d") + 1], "/work/pinned_dataset.json")
        self.assertIn(self.m.INSTANCE_SHA256[:12], cmd[cmd.index("-w") + 1])
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", cmd)

    def test_mounts_keep_host_and_container_paths_distinct(self):
        adapter = self.m.M2GenericAgentAdapter("m2-test", self.identity)
        with patch("shutil.copytree"), patch("pathlib.Path.mkdir"):
            args = adapter.container_run_args(self.m.INSTANCE_ID)
        mounts = [args[i + 1] for i, value in enumerate(args) if value == "-v"]
        self.assertTrue(any(str(self.m.GA_HOST) in item and ":/opt/genericagent:ro" in item for item in mounts))
        self.assertTrue(all("E:\\" not in item.split(":", 2)[-1] for item in mounts))

    def test_controlled_failure_prediction_has_empty_patch(self):
        with patch.object(self.m, "WORK_ROOT", Path(self._testMethodName)):
            with patch.object(self.m, "collect_reproducibility_identity", return_value={}), \
                 patch.object(self.m, "write_run_manifest"):
                path = self.m.write_controlled_failure("run")
            try:
                self.assertEqual(path.name, "predictions.jsonl")
                self.assertIn('"model_patch": ""', path.read_text(encoding="utf-8"))
            finally:
                import shutil
                shutil.rmtree(self._testMethodName)

    def test_usage_is_summed_only_for_requested_otel_run(self):
        path = Path(self._testMethodName + ".jsonl")
        def span(run, span_id, value):
            attrs = [
                {"key": "benchmark.run.id", "value": {"stringValue": run}},
                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": str(value)}},
            ]
            return {"resourceSpans": [{"scopeSpans": [{"spans": [{"spanId": span_id, "attributes": attrs}]}]}]}
        path.write_text("\n".join((json.dumps(span("target", "a", 3)), json.dumps(span("other", "b", 99)))), encoding="utf-8")
        try:
            self.assertEqual(self.m.usage_from_otel(path, "target")["input"], 3)
        finally:
            path.unlink()

    def test_claw_checkout_rejects_wrong_commit_before_use(self):
        with patch.object(self.m, "_run_checked", side_effect=["wrong", ""]):
            with self.assertRaisesRegex(RuntimeError, "commit mismatch"):
                self.m.validate_claw_checkout()

    def test_instance_hash_is_pinned(self):
        instance = {"instance_id": self.m.INSTANCE_ID, "value": 1}
        with patch.object(self.m, "INSTANCE_SHA256", self.m._canonical_sha256(instance)):
            result = self.m.validate_instance(instance)
        self.assertEqual(result["revision"], self.m.DATASET_REVISION)

    def test_workspace_uses_immutable_image_reference(self):
        original = self.m.SWEBenchWorkspace._resolve_image
        try:
            self.m.pin_workspace_image()
            self.assertEqual(self.m.SWEBenchWorkspace._resolve_image("anything"), self.m.IMAGE_REF)
        finally:
            self.m.SWEBenchWorkspace._resolve_image = staticmethod(original)

    def test_image_validation_rejects_retagged_latest(self):
        from types import SimpleNamespace
        wrong = json.dumps([{"Id": "sha256:wrong", "RepoDigests": [self.m.IMAGE_REF]}])
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=wrong, stderr="")):
            with self.assertRaisesRegex(RuntimeError, "image ID mismatch"):
                self.m.validate_image()

    def test_observed_model_is_read_from_otel(self):
        path = Path(self._testMethodName + ".jsonl")
        attrs = [
            {"key": "benchmark.run.id", "value": {"stringValue": "run"}},
            {"key": "gen_ai.request.model", "value": {"stringValue": "Actual-Model"}},
        ]
        payload = {"resourceSpans": [{"scopeSpans": [{"spans": [{"attributes": attrs}]}]}]}
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            self.assertEqual(self.m.observed_models_from_otel(path, "run"), {"actual-model"})
        finally:
            path.unlink()

    def test_run_manifest_cannot_be_overwritten(self):
        with patch.object(self.m, "WORK_ROOT", Path(self._testMethodName)):
            try:
                self.m.write_run_manifest("run", "formal_agent_run", {})
                with self.assertRaisesRegex(RuntimeError, "new run ID"):
                    self.m.write_run_manifest("run", "formal_agent_run", {})
            finally:
                import shutil
                shutil.rmtree(self._testMethodName)

    def test_evaluate_rejects_manifest_identity_mismatch(self):
        with patch.object(self.m, "WORK_ROOT", Path(self._testMethodName)):
            try:
                self.m.write_run_manifest("run", "controlled_failure", {"claw_swe": {"commit": "old"}})
                prediction = {
                    "instance_id": self.m.INSTANCE_ID,
                    "model_name_or_path": "m2-controlled-empty-patch",
                    "model_patch": "",
                }
                path = Path(self._testMethodName) / "runs" / "run" / "predictions.jsonl"
                path.write_text(json.dumps(prediction) + "\n", encoding="utf-8")
                with patch.object(
                    self.m, "collect_reproducibility_identity",
                    return_value={"claw_swe": {"commit": "current"}},
                ):
                    with self.assertRaisesRegex(RuntimeError, "identity mismatch"):
                        self.m.validate_run_manifest("run")
            finally:
                import shutil
                shutil.rmtree(self._testMethodName)


if __name__ == "__main__":
    unittest.main()
