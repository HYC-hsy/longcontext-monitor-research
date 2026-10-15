"""Selection-only v3 plans through the same PMA fake/live-host entry, never a real endpoint."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from archive_source_v2_batch import main as archive_main
from freeze_source_v2_batch import main as freeze_main
from static_source_live import authorize, run_authorized
from static_source_screen import (ASSET_REGISTRY, BATCH_SCHEMA, FakePublicTransport, HERE,
                                  PLAN_SCHEMA, asset_cases, main as screen_main,
                                  plan_slots, resolve_config, run_fake, selected_cases, sha256)

EXAMPLES = HERE / "static_plan_v3_examples"


class V3Tests(unittest.TestCase):
    def profile(self, root):
        path = root / "private.json"
        path.write_text(json.dumps({"claude_monitor_opus48": {
            "provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
            "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
            "max_tokens": 8192, "read_timeout": 300, "timeout": 30,
            "max_retries": 8, "apibase": "https://offline.invalid",
            "apikey": "SENTINEL_DO_NOT_SEND"}}), encoding="utf-8")
        return path

    def freeze(self, root, example):
        manifest, output = root / "frozen.json", root / "runs"
        argv = ["freeze_source_v2_batch.py", "--plan", str(EXAMPLES / example),
                "--manifest-out", str(manifest), "--output-root", str(output)]
        with patch("sys.argv", argv):
            freeze_main()
        self.assertFalse(output.exists())
        self.assertFalse((root / "authorization.json").exists())
        return manifest, output

    def authorize_fake(self, root, manifest, output, profile):
        auth = root / "authorization.json"
        argv = ["freeze_source_v2_batch.py", "--authorize", "--manifest-out", str(manifest),
                "--authorization-out", str(auth), "--output-root", str(output),
                "--profile", str(profile), "--authorization-source", "OFFLINE_FAKE_TEST_ONLY"]
        with patch("sys.argv", argv):
            freeze_main()
        return auth

    def fake_factory(self, manifest):
        cases = selected_cases(manifest)
        def factory(variant, slot):
            binding = next(b for b in manifest["run_bindings"] if b["run_id"] == slot.name)
            case = cases[binding["task"]]
            expected = (case["estimated_phase1_calls_per_condition"] +
                        case["estimated_phase2_calls_per_condition"])
            return FakePublicTransport(slot / "fake_wire.jsonl", expected=expected)
        return factory

    def test_same_cli_fake_single_subset_repeat_six_reordered(self):
        examples = {"single_r2.json": 1, "subset_heap.json": 2,
                    "repeat_r2.json": 2, "original_six.json": 6,
                    "reordered.json": 2}
        for name, count in examples.items():
            with self.subTest(name=name), TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "fake"
                argv = ["static_source_screen.py", "--manifest", str(EXAMPLES / name),
                        "--output", str(output), "--mode", "fake"]
                with patch("sys.argv", argv):
                    self.assertEqual(screen_main(), 0)
                rows = json.loads((output / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual(len(rows), count)
                self.assertEqual(len({row["run_id"] for row in rows}), count)
                self.assertTrue(all(row["status"] == "static_prefix_complete" for row in rows))
                self.assertTrue(all(row["provider_attempts"] == 0 for row in rows))
                self.assertEqual([(r["task"], r["variant"], r["occurrence"]) for r in rows],
                                 [(s["case_id"], s["variant"], s["occurrence"]) for s in
                                  json.loads((EXAMPLES / name).read_text())["slots"]])
                if name == "repeat_r2.json":
                    self.assertEqual(len({(output / r["run_id"] / "memory.json").resolve()
                                          for r in rows}), 2)

    def test_authorized_host_fake_subsets_and_first_request_identity(self):
        first = {}
        for name in ("single_r2.json", "subset_heap.json", "repeat_r2.json",
                     "original_six.json", "reordered.json"):
            with self.subTest(name=name), TemporaryDirectory() as directory:
                root = Path(directory)
                manifest_file, output = self.freeze(root, name)
                profile = self.profile(root)
                auth = self.authorize_fake(root, manifest_file, output, profile)
                manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                async def forbidden(**kwargs):
                    raise AssertionError("real provider boundary was not intercepted")
                with patch("litellm.acompletion", forbidden):
                    rows = asyncio.run(run_authorized(manifest_file, auth, profile, output,
                                     fake_transport_factory=self.fake_factory(manifest)))
                self.assertEqual(len(rows), len(plan_slots(manifest)))
                self.assertFalse(auth.exists())
                self.assertTrue(all(r["status"] == "static_prefix_complete" for r in rows))
                self.assertEqual(sum(r["observable_litellm_calls"] for r in rows), 0)
                for row in rows:
                    request = json.loads((output / row["run_id"] / "requests.jsonl").read_text(
                        encoding="utf-8").splitlines()[0])
                    key = (row["task"], row["variant"])
                    visible = (request["system"], request["prompt"], request["tools"])
                    if key in first:
                        self.assertEqual(visible, first[key])
                    else:
                        first[key] = visible
                if name == "repeat_r2.json":
                    self.assertNotEqual(rows[0]["run_id"], rows[1]["run_id"])
                    self.assertEqual(rows[0]["logical_phase_calls"], rows[1]["logical_phase_calls"])

    def test_terminal_failure_stops_and_archive_marks_started_without_summary(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_file, output = self.freeze(root, "subset_heap.json")
            profile = self.profile(root)
            auth = self.authorize_fake(root, manifest_file, output, profile)
            async def fail(*, prompt, system, tools=None):
                raise RuntimeError("scripted final transport failure")
            async def forbidden(**kwargs):
                raise AssertionError("real provider boundary was not intercepted")
            with patch("litellm.acompletion", forbidden):
                rows = asyncio.run(run_authorized(manifest_file, auth, profile, output,
                                                  fake_transport_factory=lambda *_: fail))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "stopped_failure")
            self.assertFalse((output / json.loads(manifest_file.read_text())["run_bindings"][1]["run_id"]).exists())
            archive = root / "archive"
            argv = ["archive_source_v2_batch.py", "--run-root", str(output),
                    "--archive-root", str(archive), "--manifest", str(manifest_file),
                    "--profile", str(profile), "--run-code-commit",
                    json.loads(manifest_file.read_text())["code_commit"]]
            with patch("sys.argv", argv):
                archive_main()
            table = json.loads((archive / "SLOT_SUMMARY.json").read_text(encoding="utf-8"))
            self.assertEqual([r["status"] for r in table], ["stopped_failure", "not_started"])
            self.assertTrue((archive / "raw_trajectories.zip").is_file())
            (output / "summary.json").unlink()
            archive2 = root / "archive2"
            argv[argv.index(str(archive))] = str(archive2)
            with patch("sys.argv", argv):
                archive_main()
            table2 = json.loads((archive2 / "SLOT_SUMMARY.json").read_text(encoding="utf-8"))
            self.assertEqual(table2[0]["status"], "started_incomplete")
            self.assertEqual(table2[1]["status"], "not_started")

    def test_invalid_selection_and_binding_refuse_before_send(self):
        base = json.loads((EXAMPLES / "single_r2.json").read_text(encoding="utf-8"))
        for mutate in (
            lambda x: x.update(slots=[]),
            lambda x: x["slots"][0].update(case_id="unknown"),
            lambda x: x["slots"][0].update(variant="R"),
            lambda x: x["slots"].append(dict(x["slots"][0], order=2)),
            lambda x: x["slots"][0].update(event_file="../escape"),
            lambda x: x["slots"][0].update(inclusive_event_sequence=99),
        ):
            data = json.loads(json.dumps(base))
            mutate(data)
            with self.assertRaises((ValueError, KeyError)):
                resolve_config(data)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_file, output = self.freeze(root, "single_r2.json")
            profile = self.profile(root)
            auth = self.authorize_fake(root, manifest_file, output, profile)
            original_bytes = manifest_file.read_bytes()
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            for field, value in (("code_commit", "wrong"), ("asset_registry_sha256", "0"*64)):
                altered = dict(manifest, **{field: value})
                manifest_file.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaises(PermissionError):
                    authorize(manifest_file, auth, output, profile)
            manifest_file.write_bytes(original_bytes)
            wrong_profile = root / "wrong-profile"
            wrong_profile.write_text("{}", encoding="utf-8")
            with self.assertRaises(PermissionError):
                authorize(manifest_file, auth, output, wrong_profile)
            with self.assertRaises(FileNotFoundError):
                authorize(manifest_file, root / "missing-authorization", output, profile)
            for mutation in (
                lambda m: m["slots"][0].update(variant="U"),
                lambda m: m["slots"].append(dict(m["slots"][0], order=2, occurrence=2)),
                lambda m: m["slots"][0].update(order=2),
                lambda m: m["asset_identities"]["fix-code-vulnerability"].update(
                    inclusive_event_sequence=40),
                lambda m: m["asset_identities"]["fix-code-vulnerability"].update(
                    event_file_sha256="0" * 64),
            ):
                altered = json.loads(original_bytes)
                mutation(altered)
                manifest_file.write_text(json.dumps(altered), encoding="utf-8")
                with self.assertRaises(PermissionError):
                    authorize(manifest_file, auth, output, profile)
            manifest_file.write_bytes(original_bytes)
            auth_bytes = auth.read_bytes()
            authorized = json.loads(auth_bytes)
            for bad_id in ("../escape", ".", ""):
                altered = json.loads(original_bytes)
                altered["run_bindings"][0]["run_id"] = bad_id
                altered["run_bindings"][0]["run_root"] = str((output / bad_id).resolve())
                manifest_file.write_text(json.dumps(altered), encoding="utf-8")
                authorized["manifest_sha256"] = sha256(manifest_file)
                authorized["run_bindings"] = altered["run_bindings"]
                auth.write_text(json.dumps(authorized), encoding="utf-8")
                with self.assertRaises(PermissionError):
                    authorize(manifest_file, auth, output, profile)
            manifest_file.write_bytes(original_bytes)
            auth.write_bytes(auth_bytes)
            output.mkdir()
            with self.assertRaises(PermissionError):
                authorize(manifest_file, auth, output, profile)
