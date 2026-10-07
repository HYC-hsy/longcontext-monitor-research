"""Mechanical archival of the two authorized fresh-history diagnostic outputs.

This script never imports the replay harness or a provider and never reads the
native evaluator. It copies completed raw records and indexes their metadata.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil


SOURCE = Path(r"E:\fresh_root_replay_execution_20261007")
HERE = Path(__file__).resolve().parent
CONDITIONS = ("simple_fresh", "spec_first_fresh")
FIXTURE_MANIFEST_SHA256 = "9480770c7aca1d8c76d43f981456c71707054e213ab529c7373fa70fdb0e941c"
WORKSPACE_SHA256 = "41efcc53fa56679bce6ed3c754a392aed60ac95110024a72b9f1c739206bda75"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def read_events(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def main() -> None:
    summary = []
    for condition in CONDITIONS:
        source = SOURCE / condition
        destination = HERE / condition
        if destination.exists():
            raise RuntimeError(f"Archive destination already exists: {destination}")
        result = json.loads((source / "RESULT.json").read_text(encoding="utf-8"))
        events = read_events(source / "review_audit.jsonl")
        if result["condition"] != condition or result["status"] != "completed":
            raise RuntimeError(f"Incomplete or mismatched run: {condition}")
        if result["fixture_identity"]["manifest_sha256"] != FIXTURE_MANIFEST_SHA256:
            raise RuntimeError("Fixture manifest mismatch")
        workspace = result["workspace"]
        if workspace["pre_tree_sha256"] != WORKSPACE_SHA256:
            raise RuntimeError("Run workspace did not start at frozen fixture identity")
        if len([event for event in events if event["event"] == "request_finished"]) != result["model_turns"]:
            raise RuntimeError("Model response count does not match result")

        destination.mkdir(parents=True)
        shutil.copy2(source / "RESULT.json", destination / "RESULT.json")
        shutil.copy2(source / "review_audit.jsonl", destination / "review_audit.jsonl")
        shutil.copytree(source / "commands", destination / "commands")

        calls = [event for event in events if event["event"] == "tool_call"]
        file_reads = []
        commands = []
        for call in calls:
            arguments = json.loads(call["arguments"])
            if call["name"] == "file_read":
                file_reads.append(arguments.get("path"))
            elif call["name"] == "code_run":
                commands.append(arguments.get("command"))
        usage = Counter()
        for event in events:
            if event["event"] == "request_usage":
                for key, value in event["usage"].items():
                    if isinstance(value, int):
                        usage[key] += value
        violation = workspace["implementation_mutation_protocol_violation"]
        summary.append({
            "condition": condition,
            "validity": "protocol_invalid" if violation else "valid",
            "model_turns": result["model_turns"],
            "tool_counts": dict(sorted(Counter(call["name"] for call in calls).items())),
            "files_read": file_reads,
            "code_commands": commands,
            "final_outcome": result["outcome"],
            "conclusion": result["conclusion"],
            "review_basis": result["review_basis"],
            "workspace_mutation_status": workspace,
            "usage": dict(sorted(usage.items())),
        })

    write_json(HERE / "MECHANICAL_AB_SUMMARY.json", summary)
    identities = {
        "harness_commit": "951e26eaa85950d23d869d966faf3cbe8c72e00a",
        "source_archive_commit": "ca3648a925eb709deb09603e36e0f4981a03743a",
        "fixture_manifest_sha256": FIXTURE_MANIFEST_SHA256,
        "workspace_tree_sha256": WORKSPACE_SHA256,
        "model": "claude-opus-4-8",
        "code_image": "sha256:42375dd7f9424cd04e3b7a19a26e9eb58d84e22c507f12a87cbac9dc12c37bff",
        "profile_file_sha256": "74c9ce480e8dee3823068a3fa32a67c1d4d99a2215d0ee909178e74911b1ee7b",
        "authorization_location": "Git-outside; not archived",
        "native_evaluator_executed": False,
        "task_agent_executed": False,
    }
    write_json(HERE / "EXECUTION_IDENTITIES.json", identities)
    files = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name != "RAW_FILE_MANIFEST.json":
            files.append({"path": path.relative_to(HERE).as_posix(),
                          "bytes": path.stat().st_size, "sha256": digest(path)})
    write_json(HERE / "RAW_FILE_MANIFEST.json", files)


if __name__ == "__main__":
    main()
