"""Mechanical Git-state certification for the restored /app checkpoint."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

from .materialize import CLEAN_GIT_HEAD, IMAGE_APP, ORIGINAL_TASK_SIDECAR


EXPECTED_HEAD_TREE = "5608e51084fb359ae0241c84acfc29cfa9095674"
EXPECTED_TURN30_STATUS = [
    " M app.go", " M app/app.go", " M menu.go", " M test/testapp.go",
    f"?? {ORIGINAL_TASK_SIDECAR}", "?? app/meta.go", "?? data/binding/sprintf.go",
    "?? theme/json.go",
]


def _git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(
        ["git", "-c", "core.filemode=false", "-C", str(root), *args],
        stderr=subprocess.DEVNULL,
    )


def certify_git_state(workspace: Path) -> dict:
    if not (workspace / ".git" / "index").is_file():
        raise RuntimeError("Restored workspace is not Git-backed")
    clean_head = _git(IMAGE_APP, "rev-parse", "HEAD").decode().strip()
    clean_tree = _git(IMAGE_APP, "rev-parse", "HEAD^{tree}").decode().strip()
    clean_index_tree = _git(IMAGE_APP, "write-tree").decode().strip()
    clean_status = _git(IMAGE_APP, "status", "--porcelain=v1", "--untracked-files=all").decode()
    if (clean_head != CLEAN_GIT_HEAD or clean_tree != EXPECTED_HEAD_TREE
            or clean_index_tree != EXPECTED_HEAD_TREE or clean_status):
        raise RuntimeError("Clean historical Git state differs")
    head = _git(workspace, "rev-parse", "HEAD").decode().strip()
    tree = _git(workspace, "rev-parse", "HEAD^{tree}").decode().strip()
    index_tree = _git(workspace, "write-tree").decode().strip()
    status = _git(workspace, "status", "--porcelain=v1", "--untracked-files=all").decode()
    status_lines = status.splitlines()
    diff = _git(workspace, "diff", "--binary")
    index_entries = _git(workspace, "ls-files", "--stage", "-z")
    if (head != CLEAN_GIT_HEAD or tree != EXPECTED_HEAD_TREE
            or index_tree != EXPECTED_HEAD_TREE or status_lines != EXPECTED_TURN30_STATUS
            or not diff):
        raise RuntimeError("Turn-30 Git state does not match public mutations")
    return {
        "git_backed_workspace": True,
        "clean_historical_head": clean_head,
        "clean_historical_head_tree": clean_tree,
        "clean_historical_index_tree": clean_index_tree,
        "clean_historical_status_porcelain_v1": clean_status,
        "turn30_head": head,
        "turn30_head_tree": tree,
        "turn30_index_tree": index_tree,
        "turn30_index_entries_sha256": hashlib.sha256(index_entries).hexdigest(),
        "turn30_status_porcelain_v1_untracked_all": status_lines,
        "turn30_git_diff_binary_sha256": hashlib.sha256(diff).hexdigest(),
        "turn30_git_diff_binary_bytes": len(diff),
        "git_diff_available": True,
        "git_command_filemode_override": "core.filemode=false (Windows extraction portability; no tracked mode changes)",
        "git_directory_sha256_scope": "separate from ordinary workspace tree SHA256",
    }
