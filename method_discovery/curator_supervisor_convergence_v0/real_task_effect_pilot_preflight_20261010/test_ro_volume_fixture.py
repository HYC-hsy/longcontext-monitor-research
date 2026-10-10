"""Zero-model Docker mount probe; never mounts a research or task checkout."""

from __future__ import annotations

import subprocess
import unittest
import uuid


IMAGE = "debian:bookworm-slim"


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], text=True, capture_output=True, timeout=45)


class ReadOnlyVolumeFixture(unittest.TestCase):
    def test_task_rw_diagnostic_ro_private_copy_and_cleanup(self):
        volume = "lc_pilot_fixture_" + uuid.uuid4().hex
        made = docker("volume", "create", volume)
        self.assertEqual(made.returncode, 0, made.stderr)
        try:
            task = docker("run", "--rm", "--network", "none", "--mount",
                          f"type=volume,source={volume},destination=/app",
                          IMAGE, "sh", "-c", "printf task-v1 >/app/source.c && test -w /app/source.c")
            self.assertEqual(task.returncode, 0, task.stderr)
            diagnostic = docker(
                "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--mount",
                f"type=volume,source={volume},destination=/app,readonly",
                "--tmpfs", "/scratch:rw,nosuid,nodev,size=16m", IMAGE, "sh", "-c",
                "test \"$(cat /app/source.c)\" = task-v1 && "
                "! (printf illegal >/app/source.c 2>/dev/null) && "
                "cp /app/source.c /scratch/source.c && "
                "printf private-v2 >/scratch/source.c && "
                "test \"$(cat /scratch/source.c)\" = private-v2 && "
                "test \"$(cat /app/source.c)\" = task-v1 && "
                "test ! -e /var/run/docker.sock && echo mount-boundary-ok")
            self.assertEqual(diagnostic.returncode, 0, diagnostic.stderr)
            self.assertEqual(diagnostic.stdout.strip(), "mount-boundary-ok")
            verify = docker("run", "--rm", "--network", "none", "--mount",
                            f"type=volume,source={volume},destination=/app,readonly",
                            IMAGE, "sh", "-c", "cat /app/source.c")
            self.assertEqual(verify.returncode, 0, verify.stderr)
            self.assertEqual(verify.stdout, "task-v1")
        finally:
            removed = docker("volume", "rm", volume)
            self.assertEqual(removed.returncode, 0, removed.stderr)
            absent = docker("volume", "inspect", volume)
            self.assertNotEqual(absent.returncode, 0)


if __name__ == "__main__":
    unittest.main()
