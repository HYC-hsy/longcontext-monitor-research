"""Mechanical redaction and readable-index check; no provider calls."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from archive_source_v2_batch import main
from static_source_live import code_commit


class ArchiveTests(unittest.TestCase):
    def test_redaction_and_file_index_include_partial_slot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            profile = root / "private.json"
            profile.write_text(json.dumps({"claude_monitor_opus48": {
                "provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
                "thinking_type": "adaptive", "reasoning_effort": "high", "temperature": 1,
                "max_tokens": 8192, "read_timeout": 300, "timeout": 30,
                "max_retries": 8, "apibase": "https://private.invalid",
                "apikey": "SENTINEL_NEVER_ARCHIVE"}}), encoding="utf-8")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"run_bindings": [{"order": 1, "task": "t",
                "variant": "S2", "run_id": "slot-1"}]}), encoding="utf-8")
            run = root / "run"
            slot = run / "slot-1"
            slot.mkdir(parents=True)
            (slot / "requests.jsonl").write_text(json.dumps({"system": "public",
                "prompt": "SENTINEL_NEVER_ARCHIVE", "tools": None}) + "\n", encoding="utf-8")
            (run / "summary.json").write_text(json.dumps([{"order": 1, "status": "stopped_failure",
                "logical_phase_calls": 1, "observable_litellm_calls": 0,
                "error_type": "RuntimeError"}]), encoding="utf-8")
            archive = root / "archive"
            argv = ["archive_source_v2_batch.py", "--run-root", str(run),
                    "--archive-root", str(archive), "--manifest", str(manifest),
                    "--profile", str(profile), "--run-code-commit", code_commit()]
            with patch("sys.argv", argv):
                main()
            sample = (archive / "REQUEST_SAMPLES.txt").read_text(encoding="utf-8")
            audit = (archive / "AUDIT_COMPLETE.txt").read_text(encoding="utf-8")
            self.assertNotIn("SENTINEL_NEVER_ARCHIVE", sample + audit)
            self.assertNotIn("https://private.invalid", sample + audit)
            self.assertIn("stopped_failure", audit)
            self.assertTrue((archive / "raw_six_slots.zip").is_file())
            self.assertIn("slot-1/requests.jsonl", (archive / "FILE_HASHES.tsv").read_text())
