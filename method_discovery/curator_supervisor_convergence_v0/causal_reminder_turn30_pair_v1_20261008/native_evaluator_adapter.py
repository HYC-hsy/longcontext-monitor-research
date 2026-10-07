"""Post-both-arm native evaluator command builder; inert until authorized."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


TASK_SOURCE = Path(r"E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks\fyn-2.2.0-roadmap")
TASK_IMAGE = "sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1"
TEST_SHA = "77637bf7eb621697259e7fad7428ed4cc578b17aef171fc76f44cf5474b8bda2"
TASK_TOML_SHA = "db81f4ee37e4f69e7ace0fa7b7cb6ab8b2cd3469463091b1bcf073da4237dd6d"


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_native_identity(task_source: Path = TASK_SOURCE) -> dict:
    if (sha_file(task_source / "tests/test.sh") != TEST_SHA
            or sha_file(task_source / "task.toml") != TASK_TOML_SHA):
        raise RuntimeError("Frozen native evaluator identity mismatch")
    return {"test_sh_sha256": TEST_SHA, "task_toml_sha256": TASK_TOML_SHA,
            "image": TASK_IMAGE, "online_available_to_task": False}


def native_command(neutral_workspace: Path, output: Path,
                   task_source: Path = TASK_SOURCE) -> list[str]:
    verify_native_identity(task_source)
    if neutral_workspace.name != "app":
        raise RuntimeError("Native input must be a label-neutral app directory")
    return ["docker", "run", "--rm", "--network", "none", "--cpus", "2",
            "--memory", "4096m", "--mount",
            f"type=bind,src={neutral_workspace.resolve().as_posix()},dst=/app",
            "--mount", f"type=bind,src={(task_source / 'tests').resolve().as_posix()},dst=/tests,readonly",
            "--mount", f"type=bind,src={output.resolve().as_posix()},dst=/logs/verifier",
            "--workdir", "/app", TASK_IMAGE, "bash", "/tests/test.sh"]


class NativeEvaluator:
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.count = 0

    def __call__(self, neutral_workspace: str) -> dict:
        self.count += 1
        if self.count > 2:
            raise RuntimeError("More than two native evaluations prohibited")
        output = self.output_root / f"evaluation_{self.count}"
        output.mkdir(parents=True, exist_ok=False)
        command = native_command(Path(neutral_workspace), output)
        (output / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
        with (output / "stdout.txt").open("wb") as stdout, (output / "stderr.txt").open("wb") as stderr:
            result = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=1800, check=False)
        return {"return_code": result.returncode, "raw_output_root": str(output),
                "test_sh_sha256": TEST_SHA, "task_toml_sha256": TASK_TOML_SHA}
