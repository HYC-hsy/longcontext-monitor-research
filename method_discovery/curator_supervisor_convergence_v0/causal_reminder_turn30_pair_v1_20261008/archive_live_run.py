"""Mechanically preserve the one authorized causal pair without interpreting it."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
SOURCE = Path(r"E:\fyne_turn30_causal_pair_v1_live_20261008_run1")
DEST = HERE / "live_run1_archive"
AUTH = HERE / "AUTHORIZATION.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))


def copy_exact(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha(source.read_bytes()) != sha(destination.read_bytes()):
        raise RuntimeError(f"Copy mismatch: {source}")


def git_bytes(workspace: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=workspace, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr[:500]!r}")
    return result.stdout


def archive_workspace(arm: str) -> dict:
    workspace = SOURCE / arm / "workspace"
    destination = DEST / arm / "workspace_final"
    destination.mkdir(parents=True, exist_ok=False)
    entries = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or ".git" in path.relative_to(workspace).parts:
            continue
        relative = path.relative_to(workspace).as_posix()
        entries.append({"path": relative, "bytes": path.stat().st_size,
                        "sha256": sha(path.read_bytes())})
    save_json(destination / "FILE_MANIFEST.json", entries)
    (destination / "GIT_HEAD.txt").write_bytes(git_bytes(workspace, "rev-parse", "HEAD"))
    (destination / "GIT_INDEX_TREE.txt").write_bytes(git_bytes(workspace, "write-tree"))
    (destination / "GIT_STATUS_PORCELAIN.bin").write_bytes(
        git_bytes(workspace, "status", "--porcelain=v1", "--untracked-files=all", "-z"))
    (destination / "TRACKED_CHANGES.patch").write_bytes(
        git_bytes(workspace, "diff", "--binary", "--no-ext-diff"))
    untracked = git_bytes(workspace, "ls-files", "--others", "--exclude-standard", "-z")
    untracked_paths = []
    for encoded in filter(None, untracked.split(b"\0")):
        relative = encoded.decode("utf-8", errors="surrogateescape")
        source = workspace / relative
        if not source.is_file():
            raise RuntimeError(f"Untracked non-file cannot be archived: {relative}")
        copy_exact(source, destination / "untracked" / relative)
        untracked_paths.append(relative)
    return {"arm": arm, "workspace_file_count": len(entries),
            "workspace_manifest_sha256": sha((destination / "FILE_MANIFEST.json").read_bytes()),
            "git_head": (destination / "GIT_HEAD.txt").read_text().strip(),
            "git_index_tree": (destination / "GIT_INDEX_TREE.txt").read_text().strip(),
            "tracked_patch_sha256": sha((destination / "TRACKED_CHANGES.patch").read_bytes()),
            "untracked_paths": untracked_paths,
            "local_full_workspace_path": str(workspace)}


def count_kind(path: Path, kind: str) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if json.loads(line).get("kind") == kind:
                count += 1
    return count


def main() -> None:
    if DEST.exists() or not AUTH.is_file():
        raise RuntimeError("Fresh archive destination and active authorization required")
    pair_file = SOURCE / "pair_result.json"
    pair = json.loads(pair_file.read_text(encoding="utf-8"))
    expected_events = ["arm_started", "arm_terminated", "arm_started", "arm_terminated",
                       "both_continuations_terminated", "native_evaluator_started_post_both",
                       "native_evaluator_started_post_both"]
    if (pair.get("status") != "continuations_complete"
            or pair.get("completed_arms") != ["control", "treatment"]
            or pair.get("native_evaluator_executed") is not True
            or [event["event"] for event in pair["events"]] != expected_events):
        raise RuntimeError("Pair terminal/order/evaluator barrier does not match protocol")
    DEST.mkdir(parents=True, exist_ok=False)
    copy_exact(AUTH, DEST / "AUTHORIZATION.json")
    copy_exact(pair_file, DEST / "pair_result.json")
    arms = {}
    for arm in ("control", "treatment"):
        for name in ("compose.json",):
            copy_exact(SOURCE / arm / name, DEST / arm / name)
        for subdir in ("raw", "stage"):
            for path in sorted((SOURCE / arm / subdir).rglob("*")):
                if path.is_file():
                    copy_exact(path, DEST / arm / subdir / path.relative_to(SOURCE / arm / subdir))
        arms[arm] = archive_workspace(arm)
        arms[arm]["provider_pre_send_count"] = count_kind(
            SOURCE / arm / "raw" / "task_raw_events.jsonl", "provider_pre_send")
        arm_result = json.loads((SOURCE / arm / "raw" / "arm_result.json").read_text(encoding="utf-8"))
        arms[arm]["termination_reason"] = arm_result["terminal_reason"]
        arms[arm]["termination_turn"] = arm_result["termination_turn"]
        arms[arm]["accepted_task_responses"] = arm_result["accepted_task_responses"]
        arms[arm]["first_provider_request_sha256"] = arm_result["first_provider_request_sha256"]
    for evaluation in ("evaluation_1", "evaluation_2"):
        for path in sorted((SOURCE / "native_evaluation" / evaluation).rglob("*")):
            if path.is_file():
                copy_exact(path, DEST / "native_evaluation" / evaluation / path.name)
    summary = {"source_run_root": str(SOURCE), "authorization_sha256": sha(AUTH.read_bytes()),
               "pair_status": pair["status"], "arms": arms,
               "native_evaluator_executed": pair["native_evaluator_executed"],
               "native_evaluator_return_codes": {
                   arm: pair["evaluations"][arm]["return_code"] for arm in ("control", "treatment")},
               "production_changes": 0, "supervisor_reviewer_pma_calls": 0}
    save_json(DEST / "RUN_MECHANICAL_SUMMARY.json", summary)
    manifest = []
    for path in sorted(DEST.rglob("*")):
        if path.is_file() and path.name != "RAW_FILE_MANIFEST.json":
            manifest.append({"path": path.relative_to(DEST).as_posix(),
                             "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())})
    save_json(DEST / "RAW_FILE_MANIFEST.json", manifest)
    print(json.dumps({"status": "archived", "archive": str(DEST),
                      "file_count": len(manifest), "manifest_sha256": sha(
                          (DEST / "RAW_FILE_MANIFEST.json").read_bytes()),
                      "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
