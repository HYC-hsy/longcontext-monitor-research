"""Preserve the fixed four-arm pilot's raw, credential-free evidence.

The original run roots remain untouched. This is an archival helper only;
it has no provider, Task, Supervisor, or evaluator execution path.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path


REPO = Path(r"E:\longcontext-cqs-v0-20261005")
DEST = REPO / "method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/live_batch2_20261011"
ARMS = ("fyne_t", "fyne_s", "kitex_s", "kitex_t")
CONTROL = Path(r"E:\pilot_live_batch2_20261011_8cfc4ef2")
AUTH = CONTROL / "AUTHORIZATION.json"
MANIFEST = CONTROL / "FYNE_KITEX_FOUR_ARM_MANIFEST_BATCH2.json"
TEXT_SUFFIXES = {".json", ".jsonl", ".txt", ".log", ".md", ".sh"}
TOKEN_RE = re.compile(rb"(?i)(?:(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}|(?:api[_-]?key|authorization)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{24,})")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def private_markers() -> set[bytes]:
    """Never print private values; only use them to prevent accidental upload."""
    profile = Path(r"E:\LongContext\monitor_config\models.local.json")
    values: set[bytes] = set()

    def visit(value, key=""):
        if isinstance(value, dict):
            for k, v in value.items():
                visit(v, str(k).lower())
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif isinstance(value, str) and len(value) >= 12 and any(
            word in key for word in ("key", "token", "secret", "password", "url", "base")
        ):
            values.add(value.encode("utf-8"))

    if profile.is_file():
        visit(json.loads(profile.read_text(encoding="utf-8")))
    return values


def check_public(path: Path, markers: set[bytes]) -> None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return
    data = path.read_bytes()
    if TOKEN_RE.search(data) or any(marker in data for marker in markers):
        raise RuntimeError(f"Potential private credential or endpoint in {path.name}; archival halted")


def main() -> None:
    if (DEST / "RAW_FILE_MANIFEST.json").exists():
        raise FileExistsError("Archive already materialized; refusing overwrite")
    markers = private_markers()
    copied: list[dict] = []
    local_only: list[dict] = []

    def copy(source: Path, relative: Path) -> None:
        if not source.is_file():
            return
        check_public(source, markers)
        target = DEST / relative
        original_sha = digest(source)
        if target.exists():
            if digest(target) != original_sha:
                raise RuntimeError(f"Existing partial archive copy differs: {relative}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        if digest(target) != original_sha:
            raise RuntimeError(f"Archive copy mismatch: {relative}")
        copied.append({"path": relative.as_posix(), "bytes": target.stat().st_size,
                       "sha256": original_sha, "source": str(source)})

    def copy_tree(source: Path, relative: Path, exclude=()) -> None:
        if not source.is_dir():
            return
        for path in sorted(source.rglob("*")):
            if path.is_file() and not any(part in exclude for part in path.relative_to(source).parts):
                copy(path, relative / path.relative_to(source))

    def compress_tar(source: Path, relative: Path) -> None:
        if not source.is_file():
            return
        target = DEST / relative
        if target.exists():
            original = hashlib.sha256()
            with gzip.open(target, "rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    original.update(chunk)
            if original.hexdigest() != digest(source):
                raise RuntimeError(f"Existing compressed partial archive differs: {relative}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open("rb") as inp, target.open("wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as out:
                    shutil.copyfileobj(inp, out, 1024 * 1024)
        local_only.append({"source": str(source), "bytes": source.stat().st_size,
                           "sha256": digest(source), "compressed_path": relative.as_posix(),
                           "compressed_bytes": target.stat().st_size,
                           "compressed_sha256": digest(target)})
        copied.append({"path": relative.as_posix(), "bytes": target.stat().st_size,
                       "sha256": digest(target), "source": str(source), "transformation": "gzip only"})

    def compress_tree(source: Path, relative: Path) -> None:
        if not source.is_dir():
            return
        target = DEST / relative
        if target.exists():
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(target, mode="w:gz", compresslevel=6) as archive:
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise RuntimeError(f"Redirected checkpoint path: {path}")
                if path.is_file():
                    check_public(path, markers)
                    archive.add(path, arcname=path.relative_to(source).as_posix(), recursive=False)
                    local_only.append({"source": str(path), "bytes": path.stat().st_size,
                                       "sha256": digest(path), "compressed_path": relative.as_posix()})
        with tarfile.open(target, mode="r:gz") as archive:
            if len(archive.getmembers()) != sum(1 for item in local_only
                                                 if item.get("compressed_path") == relative.as_posix()):
                raise RuntimeError("Checkpoint archive member count mismatch")
        copied.append({"path": relative.as_posix(), "bytes": target.stat().st_size,
                       "sha256": digest(target), "source": str(source),
                       "transformation": "tar.gz of unchanged checkpoint files"})

    copy(AUTH, Path("AUTHORIZATION.json"))
    copy(MANIFEST, Path("FYNE_KITEX_FOUR_ARM_MANIFEST_BATCH2.json"))
    for name in ("batch_control.py", "PRELAUNCH_IDENTITY.json", "BATCH_STATUS_INITIAL.json",
                 "BATCH_STATUS.json"):
        copy(CONTROL / name, Path("control") / name)
    for order in range(1, 5):
        for name in ("entry_stdout.log", "entry_stderr.log"):
            copy(CONTROL / f"{order:02d}_{name}", Path("control") / f"{order:02d}_{name}")
    for arm in ARMS:
        root = Path(rf"E:\pilot_live2_{arm}_20261011_8cfc4ef2")
        prefix = Path("arms") / arm
        copy_tree(root / "archive", prefix / "archive", exclude=("pre_evaluation_app.tar",))
        compress_tar(root / "archive/pre_evaluation_app.tar",
                     prefix / "archive/pre_evaluation_app.tar.gz")
        copy_tree(root / "monitor/task_evidence", prefix / "monitor/task_evidence")
        copy_tree(root / "monitor/monitor_private/audit", prefix / "monitor/audit",
                  exclude=("live_checkpoints",))
        for name in ("reference.md", "working.md", "delivery_feedback.jsonl"):
            copy(root / "monitor/monitor_private" / name, prefix / "monitor/private" / name)
        for name in ("completion_incomplete.json", "runtime_receipts.jsonl", "task_identity.json"):
            copy(root / "monitor" / name, prefix / "monitor" / name)
        copy_tree(root / "control/spool", prefix / "control/spool")
        copy_tree(root / "trusted/audit", prefix / "trusted/audit")
        jobs = root / "jobs" / f"pilot2-{arm.replace('_', '-')}-20261011-r1"
        copy(jobs / "result.json", prefix / "job/result.json")
        for trial in sorted(p for p in jobs.iterdir() if p.is_dir()):
            for name in ("result.json", "exception.txt", "trial.log", "config.json"):
                copy(trial / name, prefix / "job/trial" / name)
            copy_tree(trial / "agent", prefix / "job/trial/agent",
                      exclude=("failure_workspace",))
            copy_tree(trial / "verifier", prefix / "job/trial/verifier")
            copy(trial / "agent/failure_workspace/report.json",
                 prefix / "job/trial/agent/failure_workspace/report.json")
            compress_tar(trial / "agent/failure_workspace/workspace.tar",
                         prefix / "job/trial/agent/failure_workspace/workspace.tar.gz")
        compress_tree(root / "monitor/monitor_private/audit/live_checkpoints",
                      prefix / "monitor/audit/live_checkpoints.tar.gz")

    (DEST / "RAW_FILE_MANIFEST.json").write_text(
        json.dumps({"copied": copied, "local_only": local_only}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(json.dumps({"copied_files": len(copied), "copied_bytes": sum(x["bytes"] for x in copied),
                      "local_only_files": len(local_only), "largest_copied_bytes": max(x["bytes"] for x in copied)}))


if __name__ == "__main__":
    main()
