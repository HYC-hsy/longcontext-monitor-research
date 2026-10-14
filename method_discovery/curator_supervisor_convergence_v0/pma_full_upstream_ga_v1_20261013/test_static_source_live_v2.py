"""Actual v2 authorized entry, with every model boundary intercepted locally."""
import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import litellm

from freeze_source_v2_batch import main as freeze_main
import static_source_live
from static_source_live import authorize, code_commit, run_authorized
from static_source_screen import FakePublicTransport, MANIFEST_V2, ordered_slots
from memory_agent.memory import memory_agent as upstream_memory_agent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class V2EntryTests(unittest.TestCase):
    def fixture(self, root):
        manifest = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
        manifest["schema"] = "pma-source-memory-static-live-batch-v2"
        output = root / "output"
        manifest["run_bindings"] = [
            {"order": index, "task": task, "variant": variant,
             "run_id": f"new-v2-{index}",
             "run_root": str((output / f"new-v2-{index}").resolve())}
            for index, (task, variant) in enumerate(ordered_slots(manifest), 1)]
        manifest_file = root / "manifest.json"
        manifest_file.write_text(json.dumps(manifest), encoding="utf-8")
        profile = root / "private.json"
        profile.write_text(json.dumps({"claude_monitor_opus48": {
            "provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
            "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
            "max_tokens": 8192, "read_timeout": 300, "timeout": 30,
            "max_retries": 8, "apibase": "https://offline.invalid",
            "apikey": "SENTINEL_DO_NOT_SEND"}}), encoding="utf-8")
        auth = root / "authorization.json"
        auth.write_text(json.dumps({"execution_authorized": True,
            "manifest_sha256": sha(manifest_file), "code_commit": code_commit(),
            "profile_sha256": sha(profile), "run_bindings": manifest["run_bindings"],
            "output_root": str(output.resolve())}), encoding="utf-8")
        return manifest_file, auth, profile, output

    def test_six_v2_slots_use_real_runner_and_no_network(self):
        self.assertIn("vendor", str(Path(upstream_memory_agent.__file__).resolve()))
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixture(Path(directory))
            transports = []

            def fake(variant, slot):
                expected = 28 if len(transports) < 3 else 42
                transport = FakePublicTransport(slot / "fake_wire.jsonl", expected=expected)
                transports.append(transport)
                return transport

            async def forbidden(**_kwargs):
                raise AssertionError("real LiteLLM boundary was not intercepted")

            with patch("litellm.acompletion", forbidden):
                rows = asyncio.run(run_authorized(manifest, auth, profile, output,
                                                  fake_transport_factory=fake))
            self.assertEqual([r["variant"] for r in rows], ["U", "S2", "R2", "R2", "S2", "U"])
            self.assertEqual(sum(r["logical_phase_calls"] for r in rows), 210)
            self.assertEqual(sum(r["observable_litellm_calls"] for r in rows), 0)
            self.assertTrue(all(r["status"] == "static_prefix_complete" for r in rows))
            self.assertTrue(all(set(r["persisted_artifacts"]) == {
                "memory.json", "trajectory_memory.json"} for r in rows))
            self.assertFalse(auth.exists())
            for row in rows:
                slot = output / row["run_id"]
                self.assertEqual(len((slot / "requests.jsonl").read_text(encoding="utf-8").splitlines()),
                                 row["logical_phase_calls"])
                self.assertNotIn("SENTINEL_DO_NOT_SEND", (slot / "requests.jsonl").read_text(encoding="utf-8"))
            self.assertIn("source_handle", (output / "new-v2-2" / "requests.jsonl").read_text(encoding="utf-8"))
            self.assertNotIn("source_handle", (output / "new-v2-1" / "requests.jsonl").read_text(encoding="utf-8"))

    def test_wrong_order_or_missing_authorization_refuses_before_send(self):
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixture(Path(directory))
            auth.unlink()
            with self.assertRaises(FileNotFoundError):
                authorize(manifest, auth, output, profile)
            self.assertFalse(output.exists())
            data = json.loads(manifest.read_text(encoding="utf-8"))
            data["planned_order"][0]["variant"] = "R2"
            manifest.write_text(json.dumps(data), encoding="utf-8")
            auth.write_text(json.dumps({"execution_authorized": True,
                "manifest_sha256": sha(manifest), "code_commit": code_commit(),
                "profile_sha256": sha(profile), "run_bindings": data["run_bindings"],
                "output_root": str(output.resolve())}), encoding="utf-8")
            with self.assertRaises(PermissionError):
                authorize(manifest, auth, output, profile)
            self.assertFalse(output.exists())

    def test_freeze_builder_binds_code_profile_manifest_and_fresh_roots(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            _, _, profile, _ = self.fixture(root)
            manifest = root / "fresh_manifest.json"
            auth = root / "fresh_authorization.json"
            output = root / "fresh_output"
            argv = ["freeze_source_v2_batch.py", "--manifest-out", str(manifest),
                    "--authorization-out", str(auth), "--output-root", str(output),
                    "--profile", str(profile)]
            with patch("sys.argv", argv):
                freeze_main()
            data, identity = authorize(manifest, auth, output, profile)
            self.assertEqual(identity["code_commit"], code_commit())
            self.assertEqual(identity["manifest_sha256"], sha(manifest))
            self.assertEqual(len(data["run_bindings"]), 6)
            self.assertFalse(output.exists())
            with patch("sys.argv", argv), self.assertRaises(FileExistsError):
                freeze_main()

    def test_accepted_response_capture_failure_does_not_resend(self):
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixture(Path(directory))
            sends = []
            real_append = static_source_live.append_json

            async def fake_wire(**kwargs):
                sends.append(kwargs)
                return litellm.ModelResponse(model="claude-opus-4-8", choices=[{
                    "message": {"content": "", "tool_calls": []}, "finish_reason": "stop"}],
                    usage={"prompt_tokens": 1, "completion_tokens": 1})

            def fail_post_return(path, row):
                if path.name == "provider_attempts.jsonl" and row.get("outcome") == "returned":
                    raise OSError("injected capture failure after provider response")
                return real_append(path, row)

            with patch("litellm.acompletion", fake_wire), patch.object(
                    static_source_live, "append_json", fail_post_return):
                rows = asyncio.run(run_authorized(manifest, auth, profile, output))
            self.assertEqual(len(sends), 1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "stopped_failure")
            self.assertFalse(auth.exists())
            self.assertFalse((output / "new-v2-2").exists())

    def test_terminal_phase1_failure_blocks_phase2_and_later_slots(self):
        for target_order, variant in ((1, "U"), (2, "S2"), (3, "R2")):
            with self.subTest(variant=variant), TemporaryDirectory() as directory:
                manifest, auth, profile, output = self.fixture(Path(directory))
                sent = []

                def fake(current_variant, slot):
                    order = int(slot.name.rsplit("-", 1)[1])
                    if order != target_order:
                        return FakePublicTransport(slot / "fake_wire.jsonl",
                                                   expected=28)

                    async def terminal(*, prompt, system, tools=None):
                        sent.append({"variant": current_variant,
                                     "phase": "phase1" if tools is not None else "phase2"})
                        raise RuntimeError("final logical transport failure")
                    return terminal

                async def forbidden(**_kwargs):
                    raise AssertionError("network fallback forbidden")

                with patch("litellm.acompletion", forbidden):
                    rows = asyncio.run(run_authorized(manifest, auth, profile, output,
                                                      fake_transport_factory=fake))
                self.assertEqual(sent, [{"variant": variant, "phase": "phase1"}])
                self.assertEqual(len(rows), target_order)
                failed = rows[-1]
                self.assertEqual(failed["status"], "stopped_failure")
                self.assertEqual(failed["logical_phase_calls"], 1)
                self.assertEqual(failed["observable_litellm_calls"], 0)
                self.assertGreaterEqual(failed["blocked_phase_calls"], 1)
                self.assertFalse((output / f"new-v2-{target_order + 1}").exists())
                self.assertFalse(auth.exists())
                if variant != "U":
                    audit = (output / f"new-v2-{target_order}" / "episode" /
                             "candidate_audit.jsonl").read_text(encoding="utf-8")
                    self.assertIn("phase1_request_failed", audit)
                    self.assertNotIn('"status": "committed"', audit)

    def test_lower_retry_success_proceeds_to_phase2_without_extra_logical_call(self):
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixture(Path(directory))
            sends = []

            async def scripted_lower(**kwargs):
                sends.append("phase1" if kwargs.get("tools") else "phase2")
                if len(sends) == 1:
                    raise RuntimeError("transient lower failure")
                return litellm.ModelResponse(model="claude-opus-4-8", choices=[{
                    "message": {"content": "" if kwargs.get("tools") else "<no_intervention/>",
                                "tool_calls": []}, "finish_reason": "stop"}],
                    usage={"prompt_tokens": 1, "completion_tokens": 1})

            with patch("litellm.acompletion", scripted_lower):
                rows = asyncio.run(run_authorized(manifest, auth, profile, output))
            self.assertEqual(len(rows), 6)
            self.assertEqual(rows[0]["status"], "static_prefix_complete")
            self.assertEqual(rows[0]["logical_phase_calls"], 28)
            self.assertEqual(rows[0]["observable_litellm_calls"], 29)
            self.assertEqual(sends[:3], ["phase1", "phase1", "phase2"])
            self.assertEqual(rows[0]["blocked_phase_calls"], 0)
