"""Mechanical, credential-screened archive of the one completed narrow Fyne arm.

No model, tool execution, Docker, or evaluator entry exists in this module.
The original run root is read-only input; generated files go to this directory.
"""

from __future__ import annotations

import ast
import collections
import difflib
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = Path(r"E:\pilot_narrow_fyne_20261012_r1")
CONTROL_AUTH = Path(r"E:\pilot_narrow_fyne_auth_20261012\AUTHORIZATION.json")
SOURCE = Path(r"E:\LongContext\long_context_bench\.cache\m12_roadmap_tasks\fyn-2.2.0-roadmap\environment\repo")
PRIVATE_MONITOR = Path(r"E:\LongContext\monitor_config\models.local.json")
PRIVATE_TASK = Path(r"E:\LongContext\GenericAgent-main\mykey.py")
RUN_ID = "pilot-narrow-fyne-20261012-r1"
TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".log", ".md", ".sh", ".py", ".diff"}
TOKEN_RE = re.compile(rb"(?i)(?:(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|authorization)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{24,})")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def secret_markers() -> set[bytes]:
    values: set[bytes] = set()

    def visit(value, key=""):
        if isinstance(value, dict):
            for k, v in value.items():
                visit(v, str(k).lower())
        elif isinstance(value, (tuple, list)):
            for v in value:
                visit(v, key)
        elif isinstance(value, str) and len(value) >= 12 and any(
                x in key for x in ("key", "token", "secret", "password", "url", "base")):
            values.add(value.encode("utf-8"))

    visit(json.loads(PRIVATE_MONITOR.read_text(encoding="utf-8")))
    tree = ast.parse(PRIVATE_TASK.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            try:
                visit(ast.literal_eval(node))
            except (ValueError, TypeError, SyntaxError):
                pass
    return values


def check_public(path: Path, markers: set[bytes]) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return
    raw = path.read_bytes()
    if TOKEN_RE.search(raw) or any(item in raw for item in markers):
        raise RuntimeError(f"Private marker in {path.name}; archival stopped")


def rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def workspace_inventory(tar_path: Path) -> tuple[dict, dict[str, bytes]]:
    entries = []
    content = {}
    with tarfile.open(tar_path, "r:") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError("Unsafe frozen workspace member")
            if member.isfile():
                raw = archive.extractfile(member).read()
                entries.append({"path": name, "type": "file", "bytes": len(raw),
                                "sha256": hashlib.sha256(raw).hexdigest()})
                if ".git" not in Path(name).parts:
                    content[name] = raw
            elif member.issym() or member.islnk():
                entries.append({"path": name, "type": "link", "target": member.linkname})
    initial = {}
    for path in SOURCE.rglob("*"):
        if path.is_file() and not path.is_symlink() and ".git" not in path.relative_to(SOURCE).parts:
            initial[path.relative_to(SOURCE).as_posix()] = path.read_bytes()
    changed = sorted(k for k in content if k in initial and content[k] != initial[k])
    added = sorted(k for k in content if k not in initial)
    missing = sorted(k for k in initial if k not in content)
    patch = []
    binary = []
    for name in changed + added + missing:
        before, after = initial.get(name, b""), content.get(name, b"")
        try:
            if max(len(before), len(after)) > 2_000_000 or b"\0" in before + after:
                raise UnicodeError
            old = before.decode("utf-8").splitlines(keepends=True)
            new = after.decode("utf-8").splitlines(keepends=True)
        except UnicodeError:
            binary.append(name)
            continue
        patch.extend(difflib.unified_diff(old, new, fromfile="a/" + name,
                                          tofile="b/" + name))
    (HERE / "FINAL_WORKSPACE.diff").write_text("".join(patch), encoding="utf-8")
    return ({"frozen_tar_sha256": sha(tar_path), "entries": entries,
             "source_root": str(SOURCE), "changed": changed, "added": added,
             "missing": missing, "binary_or_large_diff_omitted": binary,
             "comparison_is_mechanical_not_semantic": True}, content)


def main() -> None:
    if (HERE / "RAW_FILE_MANIFEST.json").exists():
        raise FileExistsError("Single-arm archive already exists")
    markers = secret_markers()
    copied = []

    def copy(src: Path, rel: str) -> None:
        if not src.is_file():
            return
        check_public(src, markers)
        dst = HERE / rel
        if dst.exists():
            raise FileExistsError(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if sha(dst) != sha(src):
            raise RuntimeError("Copy hash mismatch: " + rel)
        copied.append({"path": rel, "bytes": dst.stat().st_size,
                       "sha256": sha(dst), "source": str(src)})

    def tree(src: Path, rel: str, *, skip=()) -> None:
        if src.is_dir():
            for path in sorted(src.rglob("*")):
                if path.is_file() and not any(x in path.relative_to(src).parts for x in skip):
                    copy(path, str(Path(rel) / path.relative_to(src)).replace("\\", "/"))

    copy(CONTROL_AUTH, "AUTHORIZATION_USED.json")
    copy(HERE / "FYNE_NARROW_SINGLE_ARM_MANIFEST.json", "control/FROZEN_MANIFEST.json")
    tree(ROOT / "archive", "raw/archive", skip=("pre_evaluation_app.tar",))
    tree(ROOT / "monitor/task_evidence", "raw/monitor/task_evidence")
    tree(ROOT / "monitor/monitor_private/audit", "raw/monitor/audit",
         skip=("live_checkpoints",))
    for name in ("reference.md", "working.md", "delivery_feedback.jsonl"):
        copy(ROOT / "monitor/monitor_private" / name, "raw/monitor/private/" + name)
    for name in ("completion_incomplete.json", "runtime_receipts.jsonl", "task_identity.json"):
        copy(ROOT / "monitor" / name, "raw/monitor/" + name)
    tree(ROOT / "control/spool", "raw/control/spool")
    tree(ROOT / "trusted/audit", "raw/trusted/audit")
    job = ROOT / "jobs" / RUN_ID
    copy(job / "result.json", "raw/job/result.json")
    for trial in sorted(x for x in job.iterdir() if x.is_dir()):
        for name in ("result.json", "exception.txt", "trial.log", "config.json"):
            copy(trial / name, "raw/job/trial/" + name)
        tree(trial / "agent", "raw/job/trial/agent", skip=("failure_workspace",))
        tree(trial / "verifier", "raw/job/trial/verifier")

    tar_path = ROOT / "archive/pre_evaluation_app.tar"
    inventory, _ = workspace_inventory(tar_path)
    (HERE / "FINAL_WORKSPACE_MANIFEST.json").write_text(
        json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gzip_path = HERE / "pre_evaluation_app.tar.gz"
    with tar_path.open("rb") as source, gzip_path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
    check = hashlib.sha256()
    with gzip.open(gzip_path, "rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            check.update(part)
    if check.hexdigest() != sha(tar_path):
        raise RuntimeError("Frozen tar compression identity mismatch")
    copied.append({"path": gzip_path.name, "bytes": gzip_path.stat().st_size,
                   "sha256": sha(gzip_path), "source": str(tar_path),
                   "transformation": "gzip byte-exact frozen tar"})

    checkpoint = ROOT / "monitor/monitor_private/audit/live_checkpoints"
    local_only = [{"source": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}
                  for path in sorted(checkpoint.rglob("*")) if path.is_file()]
    task = rows(next(job.glob("*/agent/research_events.jsonl")))
    dialogue = rows(ROOT / "monitor/monitor_private/audit/dialogue.jsonl")
    attempts = rows(ROOT / "monitor/monitor_private/audit/request_attempts.jsonl")
    usage = rows(ROOT / "monitor/monitor_private/audit/provider_usage.jsonl")
    task_events = collections.Counter(row.get("event_type") for row in task)
    monitor_events = collections.Counter(row.get("event") for row in dialogue)
    calls = collections.Counter(row.get("name") for row in dialogue
                                if row.get("event") == "tool_call")
    interventions = [dict(index=i + 1, review_id=row.get("review_id"),
                          turn=row.get("turn"), tool_id=row.get("tool_id"),
                          arguments=row.get("arguments"))
                     for i, row in enumerate(dialogue)
                     if row.get("event") == "tool_call" and row.get("name") == "intervene"]
    (HERE / "INTERVENTION_EVENT_INDEX.json").write_text(
        json.dumps(interventions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {"schema": "narrow-fyne-single-arm-mechanical-v1", "run_id": RUN_ID,
        "task_event_counts": dict(task_events), "monitor_event_counts": dict(monitor_events),
        "monitor_tool_calls_by_name": dict(calls), "monitor_request_attempts": len(attempts),
        "monitor_usage_records": len(usage), "task_terminal": json.loads(
            (ROOT / "archive/agent_end_frozen.json").read_text(encoding="utf-8"))["task_terminal"],
        "native_reward": json.loads(next(job.glob("*/verifier/reward.json")).read_text(
            encoding="utf-8")), "intervention_calls": len(interventions),
        "semantic_assessment": "not_performed"}
    (HERE / "MECHANICAL_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ("FINAL_WORKSPACE_MANIFEST.json", "FINAL_WORKSPACE.diff",
                 "INTERVENTION_EVENT_INDEX.json", "MECHANICAL_SUMMARY.json"):
        check_public(HERE / name, markers)
        copied.append({"path": name, "bytes": (HERE / name).stat().st_size,
                       "sha256": sha(HERE / name), "source": "mechanically derived"})
    (HERE / "RAW_FILE_MANIFEST.json").write_text(json.dumps({"copied": copied,
        "local_only_live_checkpoints": local_only}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    index = {"schema": "narrow-fyne-single-arm-trace-index-v1", "raw_file_manifest_sha256":
             sha(HERE / "RAW_FILE_MANIFEST.json"), "run_id": RUN_ID,
             "task_events": "raw/job/trial/agent/research_events.jsonl",
             "monitor_dialogue": "raw/monitor/audit/dialogue.jsonl",
             "monitor_requests": "raw/monitor/audit/provider_pre_send/",
             "monitor_attempts": "raw/monitor/audit/request_attempts.jsonl",
             "native_result": "raw/job/trial/verifier/reward.json",
             "workspace_manifest": "FINAL_WORKSPACE_MANIFEST.json",
             "workspace_patch": "FINAL_WORKSPACE.diff"}
    (HERE / "RAW_TRACE_INDEX.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(HERE / "RAW_TRAJECTORIES.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for row in copied:
            if row["path"].startswith("raw/"):
                archive.write(HERE / row["path"], row["path"])
    with zipfile.ZipFile(HERE / "RAW_TRAJECTORIES.zip") as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Raw ZIP CRC mismatch")
        for row in copied:
            if row["path"].startswith("raw/"):
                info = archive.getinfo(row["path"])
                if info.file_size != row["bytes"]:
                    raise RuntimeError("Raw ZIP member size mismatch")
    for row in copied:
        if (HERE / row["path"]).stat().st_size != row["bytes"] or sha(HERE / row["path"]) != row["sha256"]:
            raise RuntimeError("Archived file identity mismatch: " + row["path"])
    print(json.dumps({"copied_files": len(copied), "compressed_tar_bytes": gzip_path.stat().st_size,
                      "checkpoint_local_only_files": len(local_only),
                      "raw_manifest_sha256": sha(HERE / "RAW_FILE_MANIFEST.json"),
                      "raw_zip_sha256": sha(HERE / "RAW_TRAJECTORIES.zip"),
                      "summary": summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
