"""Create immutable, offline-only V2 acceptance logs for the frozen core package."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
DEST = PACKAGE / "evidence" / "core_contract_repair_v2"
MODULE = "method_discovery.pma_stateful_memory_v1_20261021"
COMMANDS = {
    "unittest_all": [sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(PACKAGE), "-t", str(REPO), "-p", "test_*.py", "-v"],
    "fake_scenarios": [sys.executable, "-B", "-m", MODULE + ".offline_fixture"],
    "continuous_episode": [sys.executable, "-B", "-m", "unittest",
        MODULE + ".test_multiround_v2", "-v"],
    "ga13_development": [sys.executable, "-B", "-m", "unittest",
        MODULE + ".test_ga13_dev_fixture_v2", "-v"],
}


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=REPO, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    if DEST.exists():
        raise SystemExit("Refusing to replace an existing V2 evidence directory")
    DEST.mkdir(parents=True)
    manifest = {"schema": "stateful-memory-core-contract-repair-v2",
        "code_commit": git("rev-parse", "HEAD").decode("ascii").strip(),
        "commands": {}, "files": {}, "source_identity": {},
        "transport": "FakeProvider/FakeTask only; no real model or task"}
    for label, command in COMMANDS.items():
        result = subprocess.run(command, cwd=REPO, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        for channel, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            target = DEST / f"{label}.{channel}.txt"
            target.write_bytes(raw)
            manifest["files"][target.name] = {"bytes": len(raw), "sha256": sha(raw)}
        manifest["commands"][label] = {"argv": command,
            "python_exit_code": result.returncode,
            "stdout": f"{label}.stdout.txt", "stderr": f"{label}.stderr.txt"}
    tracked = git("ls-files", "--", str(PACKAGE.relative_to(REPO))).decode(
        "utf-8").splitlines()
    for path in tracked:
        if not path.endswith(".py"):
            continue
        worktree = (REPO / path).read_bytes()
        blob = git("show", "HEAD:" + path)
        manifest["source_identity"][path] = {
            "git_blob_sha256": sha(blob), "worktree_sha256": sha(worktree),
        "git_blob_object": git("rev-parse", "HEAD:" + path).decode(
            "ascii").strip()}
    target = DEST / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False,
        sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"directory": str(DEST),
        "code_commit": manifest["code_commit"],
        "exit_codes": {key: value["python_exit_code"] for key, value in
            manifest["commands"].items()}}, sort_keys=True))
    if any(value["python_exit_code"] for value in manifest["commands"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
