"""Zero-model tests for the optional host-side Task checkpoint capture."""

import json
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

import task_recheck_capture as subject


class TaskRecheckCaptureTest(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.run = self.base / "run"
        (self.run / "archive").mkdir(parents=True)
        (self.run / "archive/agent_start_identity.json").write_text(
            json.dumps({"run_id": "run-1", "container_id": "container-1"}), encoding="utf-8")
        self.bank = self.base / "bank.json"
        self.bank.write_text('{"knowledge":[]}', encoding="utf-8")
        self.capture = self.base / "capture"

    def call(self, actor_attempt=5):
        return subject.capture_wake_boundary(
            run_root=self.run, run_id="run-1", actor_attempt=actor_attempt,
            pending_reminder="Remember source evidence", bank_file=self.bank,
            batch_rounds=4, capture_root=self.capture)

    def test_captures_each_boundary_and_binds_image_bank_and_reminder(self):
        calls = []

        def docker(*args, **_kwargs):
            calls.append(args)
            if args[:1] == ("inspect",):
                return json.dumps([{"Id": "container-1", "Image": "sha256:original",
                                    "State": {"Running": True}, "Mounts": []}])
            if args[:2] == ("image", "inspect"):
                return json.dumps([{"Id": "sha256:snapshot"}])
            if args[:1] == ("commit",):
                return "sha256:snapshot"
            raise AssertionError(args)

        with patch.object(subject, "_docker", side_effect=docker):
            self.assertEqual(self.call(actor_attempt=1)["status"], "disabled_or_initial")
            self.assertEqual(self.call(actor_attempt=4)["status"], "captured")
            result = self.call()
        self.assertEqual(result["status"], "captured")
        self.assertEqual(result["snapshot_image_id"], "sha256:snapshot")
        self.assertEqual(result["pending_reminder"], "Remember source evidence")
        self.assertEqual((self.capture / "run-1/after-step-0004/knowledge.json").read_bytes(),
                         self.bank.read_bytes())
        self.assertEqual([args[0] for args in calls],
                         ["inspect", "commit", "image", "inspect", "commit", "image"])

    def test_capture_failure_is_recorded_without_changing_bank(self):
        before = self.bank.read_bytes()
        with patch.object(subject, "_docker", side_effect=RuntimeError("unavailable")):
            result = self.call()
        self.assertEqual(result["status"], "capture_failed")
        self.assertEqual(result["error_type"], "RuntimeError")
        self.assertEqual(self.bank.read_bytes(), before)
        self.assertTrue((self.capture / "run-1/after-step-0004/capture.json").is_file())

    def test_rejects_workspace_mount_instead_of_claiming_recoverability(self):
        with patch.object(subject, "_docker", return_value=json.dumps([{
                "Id": "container-1", "Image": "sha256:original", "State": {"Running": True},
                "Mounts": [{"Destination": "/app", "Type": "bind"}]}])):
            result = self.call()
        self.assertEqual(result["status"], "capture_failed")
        self.assertIn("mounted", result["error"])
