"""Zero-model Harbor agent-package leakage and identity checks."""

import os
from pathlib import Path
import subprocess
import tempfile

import pytest

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_task_package import (
    materialize_public_agent_task,
)


@pytest.mark.parametrize("task", ["fyn-2.2.0-roadmap", "ktx-0.13.0-roadmap"])
def test_real_agent_package_has_public_assets_and_empty_verifier_mount(task):
    source_root = Path(os.environ["PILOT_TASK_SOURCE_ROOT"])
    harbor_python = Path(os.environ["PILOT_HARBOR_PYTHON"])

    source = source_root / task
    with tempfile.TemporaryDirectory(prefix="pilot-public-task-") as root:
        destination = Path(root) / task
        manifest = materialize_public_agent_task(source, destination)
        assert manifest["agent_tests_empty"] is True
        assert not (destination / "solution").exists()
        assert not list((destination / "tests").iterdir())
        assert (destination / "instruction.md").read_bytes() == (
            source / "instruction.md").read_bytes()
        assert (destination / "task.toml").read_bytes() == (
            source / "task.toml").read_bytes()
        check = subprocess.run([
            str(harbor_python), "-c",
            "from harbor.models.task.task import Task; import sys; "
            "a,b=sys.argv[1:]; assert Task.is_valid_dir(a,disable_verification=True); "
            "assert Task(a,disable_verification=True).instruction=="
            "Task(b,disable_verification=True).instruction",
            str(destination), str(source),
        ], capture_output=True, text=True, timeout=30,
           env={**os.environ, "PYTHONUTF8": "1"})
        assert check.returncode == 0, check.stderr


def test_destination_is_never_overwritten(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "instruction.md").write_text("public", encoding="utf-8")
    (source / "task.toml").write_text("[environment]\nos = 'linux'\n", encoding="utf-8")
    (source / "environment").mkdir()
    destination = tmp_path / "destination"
    destination.mkdir()
    marker = destination / "marker"
    marker.write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(FileExistsError):
        materialize_public_agent_task(source, destination)
    assert marker.read_text(encoding="utf-8") == "do not overwrite"
