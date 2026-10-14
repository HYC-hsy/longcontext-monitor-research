"""No-network tests of the authorized static branch, not the default fake branch."""
import asyncio
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from static_source_screen import FakePublicTransport, MANIFEST, verify_public_projection
from static_source_live import authorize, code_commit, run_authorized


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class StaticLiveGateTests(unittest.TestCase):
    def fixtures(self, root):
        base = json.loads(MANIFEST.read_text(encoding="utf-8"))
        base["schema"] = "pma-source-memory-static-live-batch-v1"
        base["run_bindings"] = [{"order": n, "task": case["task"], "variant": variant,
                                 "run_id": f"isolated-{n}"}
            for n, (case, variant) in enumerate(((case, variant) for case in base["cases"]
                                                   for variant in base["conditions"]), 1)]
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps(base), encoding="utf-8")
        profile = root / "private-profile.json"
        profile.write_text(json.dumps({"claude_monitor_opus48": {
            "provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
            "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
            "max_tokens": 8192, "read_timeout": 300, "timeout": 30,
            "max_retries": 8, "apibase": "https://offline.invalid", "apikey": "SENTINEL_DO_NOT_SEND"}}),
            encoding="utf-8")
        output = root / "six-slots"
        auth = root / "authorization.json"
        auth.write_text(json.dumps({"execution_authorized": True,
            "manifest_sha256": digest(manifest), "code_commit": code_commit(),
            "profile_sha256": digest(profile), "run_bindings": base["run_bindings"],
            "output_root": str(output.resolve())}), encoding="utf-8")
        return manifest, auth, profile, output

    def test_public_projection_matches_both_real_recordings(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            mapping = verify_public_projection(case)
            self.assertEqual(len(mapping["mapping"]),
                             case["estimated_phase1_calls_per_condition"])
            self.assertEqual(mapping["unexplained_differences"], [])
            self.assertEqual(sum(item.get("commands", 0) for item in mapping["mapping"]),
                             sum(item.get("tool_results", 0) for item in mapping["mapping"]))

    def test_actual_authorized_path_with_injected_fake_and_private_profile(self):
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixtures(Path(directory))
            counts = []

            def fake(variant, slot):
                expected = 28 if len(counts) < 3 else 42
                transport = FakePublicTransport(slot / "injected_fake.jsonl", expected=expected)
                counts.append(transport)
                return transport

            rows = asyncio.run(run_authorized(manifest, auth, profile, output,
                                              fake_transport_factory=fake))
            self.assertEqual(len(rows), 6)
            self.assertTrue(all(r["status"] == "static_prefix_complete" for r in rows))
            self.assertEqual(sum(r["logical_phase_calls"] for r in rows), 210)
            self.assertEqual(sum(r["observable_litellm_calls"] for r in rows), 0)
            self.assertEqual(sum(t.calls for t in counts), 210)
            self.assertFalse(auth.exists())
            self.assertNotIn("SENTINEL_DO_NOT_SEND", (output / "authorization_consumed.json").read_text())
            for row in rows:
                slot = output / row["run_id"]
                self.assertEqual(len((slot / "requests.jsonl").read_text(encoding="utf-8").splitlines()),
                                 row["logical_phase_calls"])
                self.assertEqual(len((slot / "responses.jsonl").read_text(encoding="utf-8").splitlines()),
                                 row["logical_phase_calls"])
                self.assertEqual(len((slot / "bank_states.jsonl").read_text(encoding="utf-8").splitlines()),
                                 27 if row["task"] == "custom-memory-heap-crash" else 41)
                self.assertNotIn("SENTINEL_DO_NOT_SEND", (slot / "requests.jsonl").read_text(encoding="utf-8"))

    def test_missing_or_wrong_authorization_rejected_without_output(self):
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixtures(Path(directory))
            auth.unlink()
            with self.assertRaises(FileNotFoundError):
                authorize(manifest, auth, output, profile)
            self.assertFalse(output.exists())
            auth.write_text(json.dumps({"execution_authorized": True}), encoding="utf-8")
            with self.assertRaises(PermissionError):
                authorize(manifest, auth, output, profile)
            self.assertFalse(output.exists())

    def test_caught_transport_failure_stops_batch_and_removes_authorization(self):
        with TemporaryDirectory() as directory:
            manifest, auth, profile, output = self.fixtures(Path(directory))

            async def fail(*, prompt, system, tools=None):
                raise RuntimeError("scripted transport failure")

            rows = asyncio.run(run_authorized(manifest, auth, profile, output,
                                              fake_transport_factory=lambda _variant, _slot: fail))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "stopped_failure")
            self.assertEqual(rows[0]["error_type"], "RuntimeError")
            self.assertEqual(len(rows[0]["phase_failures"]), 2)
            self.assertFalse(auth.exists())
            self.assertFalse((output / "isolated-2").exists())


if __name__ == "__main__":
    unittest.main()
