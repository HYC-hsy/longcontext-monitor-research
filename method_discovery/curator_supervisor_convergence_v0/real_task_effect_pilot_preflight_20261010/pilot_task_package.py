"""Create a public-only Harbor agent-phase task package for this pilot.

The original task is retained separately for post-agent evaluation.  Harbor
bind-mounts its task ``tests`` directory into the agent environment even when
verification is disabled, so the agent-phase package must not contain tests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize_public_agent_task(source: Path, destination: Path) -> dict:
    source = Path(source).resolve(strict=True)
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    required = ("instruction.md", "task.toml")
    if not (source / "environment").is_dir() or any(
        not (source / name).is_file() for name in required
    ):
        raise ValueError("Source task is incomplete")
    destination.mkdir(parents=True)
    try:
        for name in required:
            shutil.copy2(source / name, destination / name)
        shutil.copytree(source / "environment", destination / "environment",
                        symlinks=True)
        # Harbor's agent mount points here.  It must be empty, not a copied
        # verifier directory from the authoritative source task.
        (destination / "tests").mkdir()
        manifest = {
            "source": str(source), "destination": str(destination),
            "included": {name: _sha(destination / name) for name in required},
            "excluded": ["source/tests", "source/solution"],
            "agent_tests_empty": not any((destination / "tests").iterdir()),
        }
        if any((destination / name).exists() for name in ("solution",)):
            raise RuntimeError("Non-public answer material entered agent package")
        return manifest
    except BaseException:
        # Do not erase the failed materialization; its contents are forensic
        # evidence and the caller must choose a fresh destination.
        raise
