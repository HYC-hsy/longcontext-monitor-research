"""Actual frozen-image, no-network zero-model tool probes."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from .adapter import FakeDiagnostic, materialize, sha
from .docker_tool import DockerToolPort, IMAGE


@unittest.skipUnless(subprocess.run(["docker", "info", "--format", "{{.OSType}}"],
                                    capture_output=True, text=True, check=False).stdout.strip() == "linux",
                     "Docker Linux daemon unavailable: isolation remains uncertified")
class FrozenImageToolTests(unittest.TestCase):
    @staticmethod
    def completed(port, receipt):
        for _ in range(12):
            if receipt["status"] != "running":
                return receipt
            receipt = port.execute("code_run", {"session_id": receipt["session_id"], "wait_seconds": 1})
        raise AssertionError("analysis session did not reach a terminal receipt")

    @classmethod
    def setUpClass(cls):
        image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                               capture_output=True, text=True, check=True).stdout.strip()
        if image != IMAGE:
            raise RuntimeError("Frozen image identity mismatch")
        cls.temp = tempfile.TemporaryDirectory(prefix="static-diagnostic-docker-")
        cls.root = Path(cls.temp.name)
        for name in ("C01_B", "C01_F", "C02_B"):
            materialize(name.split("_")[0], cls.root / name)
        for directory, filename in (("host_research", "RESEARCH_MARKER"),
                                    ("host_future", "FUTURE_MARKER"),
                                    ("host_evaluator", "test.sh")):
            target = cls.root / directory
            target.mkdir()
            (target / filename).write_text("DUMMY_TEST_MARKER", encoding="utf-8")
        (cls.root / "C01_F/monitor_private/OTHER_ARM_MARKER").write_text("OTHER_ARM", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_container_probe_in_each_scene(self):
        code = (Path(__file__).parent / "probe_isolation.py").read_text(encoding="utf-8")
        for name in ("C01_B", "C02_B"):
            port = DockerToolPort(self.root / name)
            before = sha((port.app / "menu.go").read_bytes())
            receipt = self.completed(port, port.execute("code_run", {"type": "python", "code": code,
                                                                     "timeout": 60, "wait_seconds": 5}))
            self.assertEqual(receipt["status"], "success")
            content = (port.private / receipt["output_path"].removeprefix("monitor/")).read_text(encoding="utf-8")
            self.assertTrue(all(json.loads(content).values()))
            self.assertEqual(sha((port.app / "menu.go").read_bytes()), before)

    def test_separate_private_mounts_and_no_host_path_fallback(self):
        first, second = DockerToolPort(self.root / "C01_B"), DockerToolPort(self.root / "C01_F")
        first.execute("file_write", {"path": "monitor/isolated_note.txt", "content": "B-only"})
        self.assertFalse((second.private / "isolated_note.txt").exists())
        with self.assertRaises((ValueError, FileNotFoundError)):
            first.execute("file_read", {"path": "E:/research/RESEARCH_MARKER"})
        with self.assertRaises(ValueError):
            first.execute("file_patch", {"path": "task/workspace/menu.go",
                                         "old_text": "x", "new_text": "y"})
        before = sha((first.private / "reference.md").read_bytes())
        with self.assertRaises(ValueError):
            first.execute("file_write", {"path": "monitor/reference.md", "content": "x" * 16001})
        self.assertEqual(sha((first.private / "reference.md").read_bytes()), before)

    def test_history_is_never_reexecuted_or_rebound(self):
        port = DockerToolPort(self.root / "C02_B")
        session = next(iter(port.historical))
        receipt = port.execute("code_run", {"session_id": session})
        self.assertEqual(receipt["status"], "historical_completed")
        self.assertEqual(port.execute("code_run", {"session_id": "missing"})["status"], "unavailable")
        fresh = port.execute("code_run", {"type": "python", "code": "print('fresh')"})
        self.assertTrue(fresh["session_id"].startswith("static-"))
        self.assertNotIn(fresh["session_id"], port.historical)

    def test_timeout_terminates_container(self):
        port = DockerToolPort(self.root / "C01_B")
        receipt = port.execute("code_run", {"type": "bash", "code": "sleep 30", "timeout": 1})
        receipt = self.completed(port, receipt)
        self.assertEqual(receipt["status"], "error")
        self.assertEqual(receipt["reason"], "timeout")
        remaining = subprocess.run(["docker", "container", "inspect", receipt["session_id"]],
                                   capture_output=True, check=False)
        self.assertNotEqual(remaining.returncode, 0)

    def test_per_attempt_home_tmp_cache_and_output_persist_without_cross_arm_sharing(self):
        first, second = DockerToolPort(self.root / "C01_B"), DockerToolPort(self.root / "C01_F")
        write = "import os, pathlib\nfor k in ('HOME','TMPDIR','GOCACHE'):\n p=pathlib.Path(os.environ[k]); p.mkdir(parents=True,exist_ok=True); (p/'STATIC_MARKER').write_text(k)\npathlib.Path('/output/STATIC_MARKER').write_text('output')"
        self.assertEqual(self.completed(first, first.execute("code_run", {"type": "python", "code": write}))['status'], 'success')
        read = "import os, pathlib\nprint([ (pathlib.Path(os.environ[k])/'STATIC_MARKER').read_text() for k in ('HOME','TMPDIR','GOCACHE') ] + [pathlib.Path('/output/STATIC_MARKER').read_text()])"
        receipt = self.completed(first, first.execute("code_run", {"type": "python", "code": read}))
        self.assertEqual(receipt['status'], 'success')
        self.assertIn("['HOME', 'TMPDIR', 'GOCACHE', 'output']", receipt['stdout'])
        self.assertFalse((second.private / '.static_runtime/home/STATIC_MARKER').exists())
        self.assertFalse((second.private / '.static_runtime/tmp/STATIC_MARKER').exists())

    def test_fake_provider_cannot_send_and_code_run_tool_is_metered(self):
        port = DockerToolPort(self.root / "C01_B")
        controller = FakeDiagnostic("C01", backend=port)
        controller.attempt([{"name": "code_run", "arguments": {"type": "python", "code": "print(1)"}},
                            {"name": "wait", "arguments": {"after_turns": 1}}])
        self.assertEqual(controller.terminal, "wait_proposal")
        self.assertEqual(controller.tool_calls, 2)
        self.assertGreater(controller.tool_wait_seconds, 0)


if __name__ == "__main__":
    unittest.main()
