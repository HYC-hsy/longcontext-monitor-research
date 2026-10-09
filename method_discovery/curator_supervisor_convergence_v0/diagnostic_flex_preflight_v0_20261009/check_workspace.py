"""Offline replay of archived public workspace mutations; never runs task tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007 import materialize as prior
from .freeze_inputs import ARCHIVE, HERE, write_json


PUBLIC = ARCHIVE / "monitor/task_evidence/public_events.jsonl"
CUTOFFS = (120, 161)
EXPECTED_PUBLIC_SHA = "f2a007c9afa3ed8d097e249d6b96d55717066d61217c1229f823764bb6ad9441"
EXPECTED_FINAL_TAR_SHA = "e4bec1565382c5d49b4e06aa051ec909d22a2319c560c4da1b2b2341362229eb"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_from_rows(rows: list[dict]) -> str:
    return digest("".join(f"{row['path']}\0{row['sha256']}\n" for row in rows).encode("utf-8"))


def recorded_final_tar() -> tuple[str, list[dict]]:
    rows = []
    with tarfile.open(prior.SOURCE_TAR, "r") as archive:
        for member in archive:
            if not member.isfile():
                continue
            relative = member.name.removeprefix("./")
            if ".git" in Path(relative).parts:
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise RuntimeError("Unreadable final snapshot tar member")
            data = stream.read()
            rows.append({"path": relative, "bytes": len(data), "sha256": digest(data)})
    rows.sort(key=lambda row: row["path"])
    return tree_from_rows(rows), rows


def receipt_success(event: dict, call: dict) -> bool:
    receipt = next((item for item in event["tool_results"]
                    if item["tool_use_id"] == call["id"]), None)
    if receipt is None:
        raise RuntimeError(f"Mutation tool result absent at cursor {event['archive_sequence']}")
    status = json.loads(receipt["content"]).get("status")
    if status == "success":
        return True
    # At cursor 78 a file_patch returned the production no-match error before
    # its write path. This is the only failed mutation call in the archive.
    if event["archive_sequence"] == 78 and call["name"] == "file_patch" and status == "error":
        return False
    raise RuntimeError(f"Unexpected mutation result at cursor {event['archive_sequence']}")


def apply_file_mutation(workspace: Path, event: dict, call: dict) -> dict:
    if not receipt_success(event, call):
        return {"archive_sequence": event["archive_sequence"], "task_turn": event["task_turn"],
                "tool_call_id": call["id"], "tool": call["name"], "status": "error_no_write"}
    args = call["args"]
    target = prior._workspace_path(workspace, args["path"])
    if call["name"] == "file_patch":
        old, new = args["old_content"], args["new_content"]
        if "{{file:" in old or "{{file:" in new or not target.is_file():
            raise RuntimeError(f"Ambiguous patch at cursor {event['archive_sequence']}")
        with target.open("r", encoding="utf-8", newline=None) as stream:
            previous = stream.read()
        if not old or previous.count(old) != 1:
            raise RuntimeError(f"Non-unique patch at cursor {event['archive_sequence']}")
        target.write_bytes(previous.replace(old, new, 1).encode("utf-8"))
    elif call["name"] == "file_write":
        content = args.get("content")
        mode = args.get("mode", "overwrite")
        if not isinstance(content, str) or not content or "{{file:" in content:
            raise RuntimeError(f"Ambiguous write at cursor {event['archive_sequence']}")
        if mode not in ("overwrite", "append", "prepend"):
            raise RuntimeError("Unsupported file_write mode")
        old = target.read_text(encoding="utf-8") if target.is_file() and mode != "overwrite" else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        new = {"overwrite": content, "append": old + content, "prepend": content + old}[mode]
        target.write_bytes(new.encode("utf-8"))
    else:
        raise RuntimeError("Unexpected mutation tool")
    return {"archive_sequence": event["archive_sequence"], "task_turn": event["task_turn"],
            "tool_call_id": call["id"], "tool": call["name"],
            "path": target.relative_to(workspace).as_posix(),
            "sha256_after": prior.sha_file(target)}


def shell_check(events: list[dict]) -> dict:
    scripts = [(event["archive_sequence"], call["args"]["script"])
               for event in events if event["boundary"] == "post_tool_pre_next_llm"
               for call in event.get("tool_calls") or [] if call["name"] == "code_run"]
    # The frozen public log's 21 post-result shell calls through cursor 161
    # were inspected at stage 0: find/grep/ls/pwd and go build (including
    # one explicit /tmp output). This check rejects any unseen command form.
    safe_prefixes = ("pwd && find ", "ls -la", "find ", "grep ", "go build ")
    for cursor, script in scripts:
        if not script.startswith(safe_prefixes):
            raise RuntimeError(f"Unreviewed shell command at cursor {cursor}")
    with tarfile.open(prior.SOURCE_TAR, "r") as capture:
        for name in ("go.mod", "go.sum"):
            stream = capture.extractfile("./" + name)
            if stream is None or stream.read() != (prior.IMAGE_APP / name).read_bytes():
                raise RuntimeError("Go build may have changed module source")
    return {"post_result_code_run_count": len(scripts),
            "command_sequence_sha256": digest(json.dumps(scripts, ensure_ascii=False).encode()),
            "manual_command_family_review": "find/grep/ls/pwd/go build; no direct workspace write command",
            "go_mod_sum_final_equal_clean_image": True}


def main() -> None:
    if prior.sha_file(PUBLIC) != EXPECTED_PUBLIC_SHA or prior.sha_file(prior.SOURCE_TAR) != EXPECTED_FINAL_TAR_SHA:
        raise RuntimeError("Public events or retained final tar differs")
    clean_sha, clean_files = prior.source_tree(prior.IMAGE_APP, exclude_git=True)
    clean_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=prior.IMAGE_APP,
                                         text=True).strip()
    if (clean_head != prior.CLEAN_GIT_HEAD or clean_sha != prior.IMAGE_APP_TREE_SHA256
            or len(clean_files) != 2468):
        raise RuntimeError("Clean image workspace differs")
    events = [json.loads(line) for line in PUBLIC.open(encoding="utf-8")]
    if len(events) != 161 or [event["archive_sequence"] for event in events] != list(range(1, 162)):
        raise RuntimeError("Public event sequence is incomplete")
    shell = shell_check(events)
    with tempfile.TemporaryDirectory(prefix="supervisor-diagnostic-preflight-") as temporary:
        workspace = Path(temporary) / "app"
        shutil.copytree(prior.IMAGE_APP, workspace)
        if (workspace / prior.ORIGINAL_TASK_SIDECAR).exists():
            raise RuntimeError("Original-task sidecar unexpectedly in clean image")
        (workspace / prior.ORIGINAL_TASK_SIDECAR).write_bytes(prior.TASK.read_bytes())
        mutations = []
        results = {}
        for event in events:
            if event["boundary"] == "post_tool_pre_next_llm":
                for call in event.get("tool_calls") or []:
                    if call["name"] in ("file_patch", "file_write"):
                        mutations.append(apply_file_mutation(workspace, event, call))
            if event["archive_sequence"] in CUTOFFS:
                tree, rows = prior.source_tree(workspace, exclude_git=True)
                name = f"WORKSPACE_FILE_MANIFEST_CURSOR_{event['archive_sequence']}.json"
                write_json(HERE / name, rows)
                results[str(event["archive_sequence"])] = {
                    "task_turn": event["task_turn"], "boundary": event["boundary"],
                    "workspace_tree_sha256": tree, "ordinary_file_count": len(rows),
                    "file_manifest_sha256": prior.sha_file(HERE / name),
                    "replayed_mutation_count": len(mutations)}
        final_sha, final_rows = recorded_final_tar()
        replay_sha = results["161"]["workspace_tree_sha256"]
        if replay_sha != final_sha or final_rows != prior.source_tree(workspace, exclude_git=True)[1]:
            current = {row["path"]: row["sha256"] for row in prior.source_tree(workspace, exclude_git=True)[1]}
            recorded = {row["path"]: row["sha256"] for row in final_rows}
            mismatches = [path for path in sorted(current.keys() | recorded.keys())
                          if current.get(path) != recorded.get(path)]
            write_json(HERE / "WORKSPACE_REPLAY_FAILURE.json", {
                "replay_sha256": replay_sha, "retained_final_tar_tree_sha256": final_sha,
                "mismatch_paths": mismatches})
            raise RuntimeError(f"Public mutation replay differs from final tar: {len(mismatches)} paths")
    report = {"status": "workspace_replay_certified_to_final_snapshot",
              "clean_image_tree_sha256": clean_sha, "clean_git_head": clean_head,
              "retained_final_tar_sha256": EXPECTED_FINAL_TAR_SHA,
              "retained_final_tar_tree_sha256": final_sha,
              "public_events_sha256": EXPECTED_PUBLIC_SHA,
              "total_replayed_file_mutations": len(mutations),
              "shell_check": shell, "cutoffs": results}
    write_json(HERE / "WORKSPACE_REPLAY_CHECKS.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
