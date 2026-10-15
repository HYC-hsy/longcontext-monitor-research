"""Binary export of evaluator trees at the fixed official Git commit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


COMMIT = "2fd12b88aafdd04a52c298e3940bcb189f9766d6"
EXPECTED_SH = {
    "db-wal-recovery": "4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334",
    "fix-code-vulnerability": "f1611da693cb4cfc5e8482698c6a1858a5c67220ae9db89b50aed66584e9b17f",
}
EXPECTED_EXTERNAL_SH = {
    "db-wal-recovery": "88dc5c2a3abba75bca0e0f9136223ae5bb585d5984b8d9eba51a7829c1d2ba49",
    "fix-code-vulnerability": "c006a5de95b69bd78055aa26cc055734dbd50718ede25d331f767bfee4ef7f26",
}
STAGE = Path(__file__).resolve().parent / "posthoc_official_20261014"
SIX_TASKS = frozenset({
    "db-wal-recovery", "fix-code-vulnerability", "cobol-modernization",
    "custom-memory-heap-crash", "multi-source-data-merger",
    "large-scale-text-editing", "headless-terminal", "cancel-async-tasks",
})


def git(source: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(source), *args], check=True,
                          capture_output=True).stdout


def official_members(source: Path, task: str) -> list[dict]:
    """Read the fixed upstream Git blobs, never a newline-converted worktree."""
    if task not in SIX_TASKS:
        raise ValueError("unknown fixed evaluator task")
    if git(source, "cat-file", "-t", COMMIT).strip() != b"commit":
        raise RuntimeError("fixed official source commit unavailable")
    selected = []
    prefix = f"{task}/tests/"
    for row in git(source, "ls-tree", "-r", "-z", COMMIT, prefix).split(b"\0"):
        if not row:
            continue
        identity, filename = row.split(b"\t", 1)
        mode, kind, blob = identity.decode("ascii").split()
        name = filename.decode("utf-8")
        if not name.startswith(prefix) or kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError("unexpected official evaluator member")
        raw = git(source, "cat-file", "blob", blob)
        selected.append({"path": name, "mode": mode, "git_blob": blob,
                         "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                         "raw": raw})
    paths = {item["path"] for item in selected}
    if prefix + "test.sh" not in paths or len(paths) != len(selected):
        raise RuntimeError("official evaluator has no unique test.sh")
    if task in EXPECTED_SH and paths != {
            prefix + "test.sh", prefix + "test_outputs.py"}:
        raise RuntimeError("legacy official evaluator file set differs")
    script = next(item for item in selected if item["path"] == prefix + "test.sh")
    if task in EXPECTED_SH and script["sha256"] != EXPECTED_SH[task]:
        raise RuntimeError("official test.sh bytes differ from fixed source")
    if task in EXPECTED_EXTERNAL_SH:
        external = next(item for item in selected if item["path"] == prefix + "test_outputs.py")
        if external["sha256"] != EXPECTED_EXTERNAL_SH[task]:
            raise RuntimeError("official external tests differ from fixed source")
    return selected


def export_task(source: Path, task: str, target: Path) -> list[dict]:
    """Export one task into an existing empty tests directory with readback."""
    if not target.is_dir() or any(target.iterdir()):
        raise RuntimeError("official evaluator target must be an empty directory")
    members = official_members(source, task)
    for item in members:
        relative = Path(item["path"]).relative_to(Path(task) / "tests")
        if not relative.parts or ".." in relative.parts:
            raise RuntimeError("unsafe official evaluator path")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item["raw"])
        if destination.read_bytes() != item["raw"]:
            raise RuntimeError("official evaluator binary readback mismatch")
    return [{k: v for k, v in item.items() if k != "raw"} for item in members]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-git", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_git.resolve(strict=True)
    if git(source, "rev-parse", "FETCH_HEAD").decode().strip() != COMMIT:
        raise RuntimeError("official source commit mismatch")
    if STAGE.exists():
        raise FileExistsError(STAGE)
    selected = [item for task in EXPECTED_SH for item in official_members(source, task)]
    STAGE.mkdir()
    members = []
    for task in EXPECTED_SH:
        target = STAGE / task / "tests"
        target.mkdir(parents=True)
        export_task(source, task, target)
    for item in selected:
        raw = item["raw"]
        members.append({"path": item["path"], "git_blob": item["git_blob"],
                        "mode": item["mode"], "bytes": item["bytes"],
                        "sha256": item["sha256"], "crlf": raw.count(b"\r\n"),
                        "bare_lf": raw.count(b"\n") - raw.count(b"\r\n"),
                        "bare_cr": raw.count(b"\r") - raw.count(b"\r\n"),
                        "utf8_bom": raw.startswith(b"\xef\xbb\xbf")})
    provenance = {"source": "https://github.com/harbor-framework/terminal-bench-2",
                  "commit": COMMIT, "export": "git cat-file blob to binary write_bytes",
                  "members": members,
                  "amendment": "Earlier Windows worktree evaluator hashes describe newline-transformed bytes; "
                               "this independent tree restores fixed upstream Git blobs without changing prior records."}
    (STAGE / "PROVENANCE_AMENDMENT.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({"commit": COMMIT, "members": members}, indent=2))


if __name__ == "__main__":
    main()
