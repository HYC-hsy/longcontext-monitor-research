"""Zero-model, fail-closed Fyne turn-30 checkpoint materialization.

Only Git HEAD content and successful public file_write/file_patch calls through
Task turn 30 are applied. No provider, Task Agent, or evaluator is imported.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile


SOURCE_COMMIT = "ca3648a925eb709deb09603e36e0f4981a03743a"
CLEAN_GIT_HEAD = "7229e889d49c81a83b0b7e09400837f67f6ddad5"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ARCHIVE = REPO / "method_discovery/curator_supervisor_convergence_v0/crs_rhr_rer_fyne_high_budget_20261007/archive/r1"
PUBLIC_EVENTS = ARCHIVE / "monitor/task_evidence/public_events.jsonl"
RESEARCH_EVENTS = ARCHIVE / "agent/research_events.jsonl"
RUNTIME_RECEIPTS = ARCHIVE / "monitor/runtime_receipts.jsonl"
TASK = ARCHIVE / "monitor/task_evidence/original_task.txt"
CLEAN_TAR = Path(r"E:\fyne_turn30_clean_20261007.tar")
SOURCE_TAR = Path(r"E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate\bridge\crs-rhr-rer-v0-fyne-bji-high-budget-r1\evidence\pre_verification_app.tar")
CONTROL = Path(r"E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate\bridge\crs-rhr-rer-v0-fyne-bji-high-budget-r1\control")
CLEAN_SOURCE_GIT = Path(r"E:\fyne_turn30_source_20261007")
IMAGE_APP = Path(r"E:\fyne_turn30_image_app_20261007")
TASK_IMAGE = "sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1"
IMAGE_APP_TREE_SHA256 = "a78fd1e12055de14567a74114ecef238f3b9bfdec267b7f69c19607f60b38bdf"
ORIGINAL_TASK_SIDECAR = ".monitor_original_task_acae0ed0dd4346a5a1515a7586ffceed.txt"
EXPECTED = {
    PUBLIC_EVENTS: "f2a007c9afa3ed8d097e249d6b96d55717066d61217c1229f823764bb6ad9441",
    RESEARCH_EVENTS: "da03831f6382ea7a02ebe5b71e9c3907bad71d60c01926ed95e784415be60082",
    RUNTIME_RECEIPTS: "5b25a1e66a1bbe4512cdfd9f3059f7c5a522dd5d9b5bcca3c8e77acd1480eadf",
    TASK: "cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080",
    CLEAN_TAR: "e3ee9bcc91498422df09fb974a655554e3f7a42e1016a01510bb6d84e8bca49e",
    SOURCE_TAR: "e4bec1565382c5d49b4e06aa051ec909d22a2319c560c4da1b2b2341362229eb",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify_sources() -> None:
    if subprocess.check_output(["git", "cat-file", "-t", SOURCE_COMMIT], cwd=REPO, text=True).strip() != "commit":
        raise RuntimeError("Source commit not available")
    for path, expected in EXPECTED.items():
        if sha_file(path) != expected:
            raise RuntimeError(f"Source hash mismatch: {path}")
        if path.is_relative_to(REPO):
            relative = path.relative_to(REPO).as_posix()
            committed = subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:{relative}"], cwd=REPO)
            if sha_bytes(committed) != expected:
                raise RuntimeError(f"Source commit file mismatch: {relative}")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CLEAN_SOURCE_GIT, text=True).strip()
    if head != CLEAN_GIT_HEAD:
        raise RuntimeError("Clean source Git HEAD mismatch")
    image = subprocess.check_output(["docker", "image", "inspect", TASK_IMAGE,
                                     "--format", "{{.Id}}"], text=True).strip()
    if image != TASK_IMAGE:
        raise RuntimeError("Clean task image identity mismatch")
    image_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=IMAGE_APP, text=True).strip()
    if image_head != CLEAN_GIT_HEAD:
        raise RuntimeError("Clean image /app Git HEAD mismatch")
    if source_tree(IMAGE_APP, exclude_git=True)[0] != IMAGE_APP_TREE_SHA256:
        raise RuntimeError("Clean image /app tree identity mismatch")
    source_manifest = json.loads((ARCHIVE / "RAW_FILE_MANIFEST.json").read_text(encoding="utf-8"))
    if not any(row["sha256"] == EXPECTED[SOURCE_TAR] and Path(row["path"]) == SOURCE_TAR
               for row in source_manifest["local_only_large_artifacts"]):
        raise RuntimeError("Retained source snapshot not bound to accepted archive")


def source_tree(root: Path, exclude_git: bool = False) -> tuple[str, list[dict]]:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError("Workspace symlink unsupported")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if exclude_git and ".git" in path.relative_to(root).parts:
                continue
            rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha_file(path)})
    rows.sort(key=lambda row: row["path"])
    data = "".join(f"{row['path']}\0{row['sha256']}\n" for row in rows).encode("utf-8")
    return sha_bytes(data), rows


def _safe_member(name: str) -> PurePosixPath:
    relative = PurePosixPath(name.removeprefix("./"))
    if relative.is_absolute() or not relative.parts or any(p in (".", "..") for p in relative.parts):
        raise RuntimeError(f"Unsafe clean archive member: {name}")
    return relative


def _extract_clean(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tarfile.open(CLEAN_TAR, "r") as source:
        for member in source:
            if member.isdir():
                continue
            if not member.isfile():
                raise RuntimeError(f"Unsupported clean archive member: {member.name}")
            relative = _safe_member(member.name)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = source.extractfile(member)
            if stream is None:
                raise RuntimeError(f"Unreadable clean archive member: {member.name}")
            target.write_bytes(stream.read())


def _workspace_path(destination: Path, task_path: str) -> Path:
    if not task_path.startswith("/app/"):
        raise RuntimeError(f"Unsupported public workspace path: {task_path}")
    relative = PurePosixPath(task_path.removeprefix("/app/"))
    if not relative.parts or any(p in (".", "..") for p in relative.parts):
        raise RuntimeError(f"Unsafe public workspace path: {task_path}")
    return destination.joinpath(*relative.parts)


def _check_shell_calls(events: list[dict]) -> None:
    allowed = {
        'pwd && find . -type f -name "*.go" | head -30',
        'ls -la',
        'find widget -name "*.go" -type f | grep -E "(toolbar|hyperlink|entry)" | head -10',
        'find data -name "*.go" -type f | head -15',
        'find driver -name "*.go" -type f | head -10',
        'ls -la app/', 'ls -la data/validation/', 'ls -la theme/',
        'go build -o /tmp/fyne_test ./app 2>&1 | head -20',
    }
    build_seen = False
    for event in events:
        if event["task_turn"] > 30 or event["boundary"] != "post_tool_pre_next_llm":
            continue
        for call in event["tool_calls"]:
            if call["name"] == "code_run" and call["args"].get("script") not in allowed:
                raise RuntimeError(f"Unsupported shell mutation risk at turn {event['task_turn']}")
            if call["name"] == "code_run" and call["args"].get("script", "").startswith("go build -o /tmp/"):
                build_seen = True
    if build_seen:
        # This failed build targeted /tmp. Check the two Go module files that
        # such a command may update: the SHA-bound pre-evaluator capture has
        # their original bytes, and no later public file tool touched them.
        if any(call["name"] in ("file_patch", "file_write")
               and call["args"].get("path") in ("/app/go.mod", "/app/go.sum")
               for event in events for call in event.get("tool_calls", [])):
            raise RuntimeError("Go module file was later rewritten; build side effect cannot be isolated")
        with tarfile.open(SOURCE_TAR, "r") as capture:
            for name in ("go.mod", "go.sum"):
                stream = capture.extractfile("./" + name)
                if stream is None or stream.read() != (IMAGE_APP / name).read_bytes():
                    raise RuntimeError("Go build may have mutated workspace module state")


def materialize(destination: Path) -> dict:
    verify_sources()
    if destination.exists():
        raise RuntimeError("Checkpoint destination exists; refusing overwrite")
    events = jsonl(PUBLIC_EVENTS)
    _check_shell_calls(events)
    # The historical /app was Git-backed. Preserve that exact clean-image
    # repository before replaying public mutations; .git is not model-hidden.
    shutil.copytree(IMAGE_APP, destination)
    base_tree, base_files = source_tree(destination, exclude_git=True)
    if len(base_files) != 2468 or base_tree != IMAGE_APP_TREE_SHA256:
        raise RuntimeError("Clean image workspace identity mismatch")
    # Turn-2 public ls proves this task-text sidecar predated the checkpoint.
    # Source bytes are cross-checked against the retained pre-evaluator tar,
    # not taken from the later implementation state.
    with tarfile.open(SOURCE_TAR, "r") as capture:
        stream = capture.extractfile("./" + ORIGINAL_TASK_SIDECAR)
        if stream is None or stream.read() != TASK.read_bytes():
            raise RuntimeError("Historical original-task sidecar identity mismatch")
    if (IMAGE_APP / ORIGINAL_TASK_SIDECAR).exists():
        raise RuntimeError("Sidecar unexpectedly present in clean image")
    (destination / ORIGINAL_TASK_SIDECAR).write_bytes(TASK.read_bytes())
    mutations = []
    for event in events:
        if event["task_turn"] > 30 or event["boundary"] != "post_tool_pre_next_llm":
            continue
        for call in event["tool_calls"]:
            if call["name"] not in ("file_patch", "file_write"):
                continue
            receipt = next((result for result in event["tool_results"]
                            if result["tool_use_id"] == call["id"]), None)
            if receipt is None or json.loads(receipt["content"]).get("status") != "success":
                raise RuntimeError(f"Unsuccessful/unmatched file mutation at turn {event['task_turn']}")
            args = call["args"]
            target = _workspace_path(destination, args["path"])
            if call["name"] == "file_write":
                if target.exists() or not isinstance(args.get("content"), str):
                    raise RuntimeError("Ambiguous file_write target/content")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(args["content"].encode("utf-8"))
            else:
                old = args["old_content"]
                new = args["new_content"]
                # The original Linux text tool used universal-newline text I/O:
                # first patching a CRLF Git file rewrote that file with LF bytes.
                with target.open("r", encoding="utf-8", newline=None) as stream:
                    previous = stream.read()
                if not old or previous.count(old) != 1:
                    raise RuntimeError(f"Ambiguous file_patch at turn {event['task_turn']}: {args['path']}")
                target.write_bytes(previous.replace(old, new, 1).encode("utf-8"))
            mutations.append({"task_turn": event["task_turn"], "archive_sequence": event["archive_sequence"],
                              "tool": call["name"], "tool_call_id": call["id"],
                              "path": target.relative_to(destination).as_posix(), "sha256_after": sha_file(target)})
    tree, files = source_tree(destination, exclude_git=True)
    return {"source_commit": SOURCE_COMMIT, "clean_git_head": CLEAN_GIT_HEAD,
            "task_image": TASK_IMAGE, "clean_image_tree_sha256": base_tree,
            "workspace_tree_sha256": tree, "workspace_file_count": len(files),
            "mutations": mutations, "files": files}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = materialize(args.destination)
    print(json.dumps({"workspace_tree_sha256": result["workspace_tree_sha256"],
                      "workspace_file_count": result["workspace_file_count"],
                      "mutation_count": len(result["mutations"])}, ensure_ascii=False))
