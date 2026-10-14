"""One-use, strictly serial launcher for the frozen PMA/GA four-arm pilot.

The controller never interprets reward. It only uses persisted mechanical
status and stops on any failure whose isolation cannot be established.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from .live_launcher import live_status_success
from .pma_harbor_hooks import verify_live_spec
from .six_task_plan import validate_plan


EXPECTED = ((1, "db-wal-recovery", "A"),
            (2, "db-wal-recovery", "B"),
            (3, "fix-code-vulnerability", "B"),
            (4, "fix-code-vulnerability", "A"))


def disposition(status: dict | None, run_root: Path, *, require_native: bool = False) -> str:
    if status is None or status.get("cleanup_confirmed") is not True:
        return "stop_batch_cleanup_or_status_unknown"
    if status.get("remaining_containers") != [] or status.get("cleanup_errors"):
        return "stop_batch_cleanup_unknown"
    if status.get("primary_failure"):
        return "stop_batch_shared_runtime_unknown"
    if require_native and status.get('native_result') is None:
        return 'stop_batch_native_evaluation_unavailable'
    if (status.get('native_result') is not None and
            status['native_result'].get('status') != 'native_recorded'):
        return 'stop_batch_native_evaluation_unavailable'
    if not (run_root / "archive" / "agent_start_identity.json").is_file():
        return "stop_batch_identity_unconfirmed"
    if live_status_success(status):
        return "completed"
    # A nonzero Harbor status after authenticated agent start and confirmed
    # cleanup is retained as a local technical outcome, never retried.
    return "arm_failed_isolated"


def run_batch(args: argparse.Namespace) -> dict:
    manifest_path = Path(args.manifest).resolve(strict=True)
    authorization_path = Path(args.authorization).resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    granted = json.loads(authorization_path.read_text(encoding="utf-8"))
    six_task = manifest.get("schema") == "pma-ga-live-manifest-v2"
    if six_task:
        bindings = validate_plan(manifest, granted)
    else:
        arms = manifest.get("arms")
        bindings = granted.get("run_bindings")
        if ([(a.get("order"), a.get("task"), a.get("condition")) for a in arms] !=
                list(EXPECTED) or
                [(b.get("order"), b.get("task"), b.get("condition")) for b in bindings] !=
                list(EXPECTED)):
            raise RuntimeError("frozen four-arm order differs")
    if any(Path(binding["run_root"]).exists() for binding in bindings):
        raise RuntimeError("one or more run roots already exist")
    # Reuse the same exact authorization, commit and binding check that the
    # Harbor subprocess performs; it is rechecked there on every arm.
    import hashlib
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    auth_hash = hashlib.sha256(authorization_path.read_bytes()).hexdigest()
    first = bindings[0]
    verify_live_spec(dict(schema="pma-ga-live-run-v1", mode="authorized_live",
        manifest_path=str(manifest_path), manifest_sha256=manifest_hash,
        authorization_path=str(authorization_path), authorization_sha256=auth_hash,
        audited_code_commit=granted["audited_code_commit"], task_id=first["task"],
        **first))
    record = {"schema": "pma-ga-batch-result-v2" if six_task else "pma-ga-batch-result-v1", "arms": [],
              "not_started": [], "stop_reason": None}
    output = Path(args.batch_result).resolve(strict=False)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    common = ["--manifest", str(manifest_path), "--authorization", str(authorization_path),
              "--ga-source", args.ga_source, "--runtime-root", args.runtime_root,
              "--task-profile-file", args.task_profile_file,
              "--worker-python", args.worker_python, "--harbor-python", args.harbor_python,
              "--bench-root", args.bench_root, "--python-home", args.python_home,
              "--official-source-git", args.official_source_git]
    if args.pma_profile_file:
        common += ["--pma-profile-file", args.pma_profile_file]
    if six_task:
        if not args.harbor_source_root:
            raise RuntimeError('six-task clean native Harbor source is required')
        common += ["--harbor-source-root", args.harbor_source_root]
    for index, binding in enumerate(bindings):
        root = Path(binding["run_root"])
        command = [sys.executable, "-m",
            "method_discovery.curator_supervisor_convergence_v0."
            "pma_full_upstream_ga_v1_20261013.live_launcher", *common,
            "--order", str(binding["order"]), "--task", binding["task"],
            "--condition", binding["condition"], "--run-id", binding["run_id"],
            "--run-root", binding["run_root"]]
        if six_task:
            command += ["--repeat", str(binding["repeat"])]
        completed = subprocess.run(command, check=False)
        result_path = root / "archive" / "live_result.json"
        try:
            status = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            status = None
        outcome = disposition(status, root, require_native=six_task)
        if completed.returncode == 0 and outcome != "completed":
            outcome = "stop_batch_exit_status_disagrees"
        record["arms"].append({"order": binding["order"], "run_id": binding["run_id"],
                               "run_root": str(root), "launcher_exit": completed.returncode,
                               "disposition": outcome, "status": status})
        output.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        if outcome.startswith("stop_batch"):
            record["stop_reason"] = outcome
            record["not_started"] = bindings[index + 1:]
            break
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in ("manifest", "authorization", "ga-source", "runtime-root",
                 "task-profile-file", "worker-python", "harbor-python", "bench-root",
                 "official-source-git", "batch-result"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--pma-profile-file")
    parser.add_argument("--harbor-source-root")
    parser.add_argument("--python-home", default="cpython-3.12.12-linux-x86_64-gnu")
    record = run_batch(parser.parse_args())
    print(json.dumps({"completed_or_attempted": len(record["arms"]),
                      "not_started": len(record["not_started"]),
                      "stop_reason": record["stop_reason"]}))
    if record["stop_reason"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
