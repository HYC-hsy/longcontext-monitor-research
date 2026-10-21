"""Immutable V3 fake-only acceptance capture; refuses an existing directory."""

import json
import subprocess
import sys

from .run_offline_acceptance_v2 import PACKAGE, REPO, git, sha


DEST = PACKAGE / "evidence" / "core_contract_closure_v3"
MODULE = "method_discovery.pma_stateful_memory_v1_20261021"
COMMANDS = {
    "unittest_all": [sys.executable, "-B", "-m", "unittest", "discover",
        "-s", str(PACKAGE), "-t", str(REPO), "-p", "test_*.py", "-v"],
    "core_v3": [sys.executable, "-B", "-m", "unittest",
        MODULE + ".test_core_contract_closure_v3", "-v"],
    "fake_scenarios": [sys.executable, "-B", "-m", MODULE + ".offline_fixture"],
    "continuous_episode": [sys.executable, "-B", "-m", "unittest",
        MODULE + ".test_multiround_v2", "-v"],
    "ga13_development": [sys.executable, "-B", "-m", "unittest",
        MODULE + ".test_ga13_dev_fixture_v3", "-v"],
}


def main() -> None:
    if DEST.exists():
        raise SystemExit("Refusing to replace existing V3 raw evidence")
    DEST.mkdir(parents=True)
    manifest = {"schema": "stateful-memory-core-contract-closure-v3",
        "tested_commit": git("rev-parse", "HEAD").decode("ascii").strip(),
        "transport": "offline FakeProvider/FakeTask only", "commands": {},
        "files": {}, "source_identity": {}}
    for label, command in COMMANDS.items():
        result = subprocess.run(command, cwd=REPO, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=240)
        manifest["commands"][label] = {"argv": command,
            "python_exit_code": result.returncode,
            "stdout": label + ".stdout.txt", "stderr": label + ".stderr.txt"}
        for channel, raw in (("stdout", result.stdout), ("stderr", result.stderr)):
            target = DEST / f"{label}.{channel}.txt"
            target.write_bytes(raw)
            manifest["files"][target.name] = {"bytes": len(raw), "sha256": sha(raw)}
    tracked = git("ls-files", "--", str(PACKAGE.relative_to(REPO))).decode(
        "utf-8").splitlines()
    for path in tracked:
        if not path.endswith(".py"):
            continue
        blob = git("show", "HEAD:" + path)
        worktree = (REPO / path).read_bytes()
        manifest["source_identity"][path] = {"git_blob_sha256": sha(blob),
            "worktree_sha256": sha(worktree),
            "git_blob_object": git("rev-parse", "HEAD:" + path).decode(
                "ascii").strip()}
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2,
        ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"tested_commit": manifest["tested_commit"],
        "directory": str(DEST), "exit_codes": {key: value[
            "python_exit_code"] for key, value in manifest["commands"].items()}},
        sort_keys=True))
    if any(value["python_exit_code"] for value in manifest["commands"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
