"""Unarmed PMA/GA Harbor fixture.  There is deliberately no live mode here."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from long_context_bench.scripts.isolated_run_bundle import build_bundle, digest_tree
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_offline_harbor import _offline_gateway
from .six_task_assets import materialize_public


TASKS = {
    "db-wal-recovery": "alexgshaw/db-wal-recovery:20251031",
    "fix-code-vulnerability": "alexgshaw/fix-code-vulnerability:20251031",
    "cobol-modernization": "alexgshaw/cobol-modernization:20251031",
    "custom-memory-heap-crash": "alexgshaw/custom-memory-heap-crash:20251031",
    "multi-source-data-merger": "alexgshaw/multi-source-data-merger:20251031",
    "large-scale-text-editing": "alexgshaw/large-scale-text-editing:20251031",
}
STAGE = Path(__file__).resolve().parent


def image_identity(tag: str) -> dict:
    result = subprocess.run(["docker", "image", "inspect", tag], capture_output=True,
                            text=True, timeout=30, check=True)
    row = json.loads(result.stdout)[0]
    return {"image_id": row["Id"], "repo_digests": row.get("RepoDigests") or [],
            "platform": f"{row['Os']}/{row['Architecture']}"}


def capture_mounts(root: Path, *, include_stopped: bool = False) -> list[dict]:
    """Read actual Compose containers, never infer isolation from path names."""
    found = []
    listed = subprocess.run(["docker", "ps", "-aq" if include_stopped else "-q"], capture_output=True,
                            text=True, timeout=10, check=True)
    for container in listed.stdout.splitlines():
        inspected = subprocess.run(["docker", "inspect", container], capture_output=True,
                                   text=True, timeout=10, check=True)
        row = json.loads(inspected.stdout)[0]
        config_files = row.get("Config", {}).get("Labels", {}).get(
            "com.docker.compose.project.config_files", "")
        if str(root / "bundle" / "isolation.compose.json") not in config_files:
            continue
        found.append({"id": row["Id"], "name": row["Name"],
                      "image_id": row["Image"],
                      "network_mode": row.get("HostConfig", {}).get("NetworkMode"),
                      "mounts": [{"source": m.get("Source"), "destination": m.get("Destination"),
                                  "rw": m.get("RW"), "type": m.get("Type"),
                                  "name": m.get("Name")}
                                 for m in row.get("Mounts", [])]})
    return found


def clean_owned_containers(root: Path) -> list[str]:
    """Remove only Compose resources whose config path is this fresh run."""
    errors = []
    for row in capture_mounts(root, include_stopped=True):
        removed = subprocess.run(["docker", "rm", "-f", row["id"]],
                                 capture_output=True, text=True, timeout=30)
        if removed.returncode:
            errors.append(f"remove_failed:{row['id']}")
            continue
        checked = subprocess.run(["docker", "inspect", row["id"]],
                                 capture_output=True, text=True, timeout=30)
        if checked.returncode == 0 or "no such object" not in checked.stderr.lower():
            errors.append(f"removal_unconfirmed:{row['id']}")
    return errors


def _prepare_common(args, *, fake_gateway: bool) -> dict:
    if args.task not in TASKS or args.condition not in {"A", "B"}:
        raise ValueError("unsupported PMA fixture arm")
    root = Path(args.run_root).resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    (root / "control").mkdir()
    (root / "archive").mkdir()
    manifest_path = (STAGE / "FOUR_RUN_MANIFEST_DRAFT.json" if fake_gateway
                     else Path(args.manifest).resolve(strict=True))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    task = root / "public_task"
    if not fake_gateway and manifest.get("schema") == "pma-ga-live-manifest-v2":
        materialize_public(Path(args.official_source_git).resolve(strict=True),
                           args.task, task, manifest["assets"][args.task]["public_members"])
    else:
        shutil.copytree(STAGE / "assets" / "public" / args.task, task)
    (task / "tests").mkdir(exist_ok=True)
    (task / "solution").mkdir(exist_ok=True)
    # Task only receives the public task package. The fixed PMA source and
    # private memory archive never appear in a Compose or Harbor mount.
    ga_source = Path(args.ga_source).resolve(strict=True)
    ga_stage = root / "control" / "ga_stage"
    shutil.copytree(ga_source, ga_stage, ignore=shutil.ignore_patterns(
        ".git", "temp", "tests", "__pycache__", ".pytest_cache", "*.pyc",
        "*.local.json", "file_access_stats.json", "mykey.py"))
    shutil.copy2(Path(args.task_profile_file).resolve(strict=True), ga_stage / "mykey.py")
    runtime = Path(args.runtime_root).resolve(strict=True)
    source, compose = build_bundle(root / "bundle", ga_stage, runtime,
                                   args.python_home, args.task_profile, None, 15340,
                                   task_network_policy=("official" if not fake_gateway and
                                       manifest.get("schema") == "pma-ga-live-manifest-v2"
                                       else "isolated"))
    if fake_gateway:
        _offline_gateway(root, runtime, args.python_home)
    if fake_gateway and getattr(args, "multiturn_fixture", False):
        fake_compose = json.loads(compose.read_text(encoding="utf-8"))
        fake_compose["services"]["model-gateway"]["environment"] = {
            "PMA_MULTITURN_FIXTURE": "1"}
        compose.write_text(json.dumps(fake_compose, indent=2), encoding="utf-8")
    if manifest["execution_authorized"] is not False:
        raise RuntimeError("PMA draft unexpectedly authorized")
    identity = image_identity(TASKS[args.task])
    if not fake_gateway:
        approved = manifest['assets'][args.task]
        if (identity['image_id'] != approved['image_id'] or
                approved['repo_digest'] not in identity['repo_digests']):
            raise RuntimeError('PMA target image differs from frozen live manifest')
    for name in ("requests", "responses"):
        (root / "control" / "spool" / name).mkdir(parents=True, exist_ok=False)
    config = json.loads(compose.read_text(encoding="utf-8"))
    if args.condition == "B":
        main = config["services"]["main"]
        main["volumes"] += [
            {"type": "bind", "source": (root / "control" / "spool" / "requests").as_posix(),
             "target": "/run/pma-bridge/requests", "read_only": False},
            {"type": "bind", "source": (root / "control" / "spool" / "responses").as_posix(),
             "target": "/run/pma-bridge/responses", "read_only": True},
        ]
    compose.write_text(json.dumps(config, indent=2), encoding="utf-8")
    record = {"schema": ("pma-ga-offline-harbor-v1" if fake_gateway else
                          "pma-ga-live-prepared-v1"), "execution_authorized": False,
              "run_id": args.run_id, "task": args.task, "condition": args.condition,
              "image": TASKS[args.task], **identity,
              "public_task_tree_sha256": digest_tree(task),
              "ga_bundle_tree_sha256": digest_tree(source),
              "source_profile_file_sha256": hashlib.sha256(
                  Path(args.task_profile_file).read_bytes()).hexdigest(),
              "worker_private_mounted": "not_yet_inspected",
              "network_mode": ("official_requested" if not fake_gateway and
                  manifest.get("schema") == "pma-ga-live-manifest-v2"
                  else "none_requested"),
              "native_evaluator_calls": 0, "fake_provider_only": fake_gateway}
    (root / "archive" / "prepared.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    return record


def prepare(args) -> dict:
    if args.execution_authorized:
        raise ValueError("offline launcher cannot authorize model execution")
    return _prepare_common(args, fake_gateway=True)


def run_offline(args) -> dict:
    record = prepare(args)
    root = Path(args.run_root).resolve(strict=True)
    deadline = time.time() + args.timeout_sec
    worker = None
    harbor = None
    worker_stdout = worker_stderr = None
    result = None
    primary_failure = None
    cleanup_errors = []
    try:
        if args.condition == "B":
            worker_stdout = (root / "archive" / "worker.stdout.log").open("wb")
            worker_stderr = (root / "archive" / "worker.stderr.log").open("wb")
            env = dict(os.environ)
            env["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
            env["PYTHONPATH"] = os.pathsep.join((str(STAGE),
                str(STAGE / "vendor" / "pma_89e5c0d" / "src"),
                str(STAGE / "vendor" / "pma_89e5c0d" / "external" / "harbor" / "src")))
            command = [str(Path(args.worker_python).resolve(strict=True)),
                       str(STAGE / "worker_main.py"), "--run-id", args.run_id,
                       "--task-id", args.task, "--private-root", str(root / "host_private"),
                       "--requests", str(root / "control" / "spool" / "requests"),
                       "--responses", str(root / "control" / "spool" / "responses"),
                       "--deadline-epoch", str(deadline), "--fake-memory"]
            if getattr(args, "multiturn_fixture", False):
                command.append("--fake-memory-update")
            worker = subprocess.Popen(command, cwd=STAGE, env=env,
                                      stdout=worker_stdout, stderr=worker_stderr)
            ready = root / "host_private" / "worker_ready.json"
            ready_deadline = min(deadline, time.time() + 10)
            while not ready.is_file():
                if worker.poll() is not None or time.time() >= ready_deadline:
                    raise RuntimeError("offline PMA worker did not become ready")
                time.sleep(.05)
            worker_record = json.loads(ready.read_text(encoding="utf-8"))
            if (worker_record["run_id"], worker_record["task_id"]) != (args.run_id, args.task):
                raise RuntimeError("offline PMA worker identity mismatch")
        mounts = [
            {"type": "bind", "source": str(Path(args.runtime_root).resolve(strict=True)),
             "target": "/opt/m4-runtime", "read_only": True},
            {"type": "bind", "source": str((root / "bundle" / "source").resolve(strict=True)),
             "target": "/opt/genericagent-source", "read_only": True},
        ]
        command = [str(Path(args.harbor_exe).resolve(strict=True)), "jobs", "start",
                   "--job-name", args.run_id, "--jobs-dir", str(root / "jobs"),
                   "--path", str(root / "public_task"),
                   "--agent", ("method_discovery.curator_supervisor_convergence_v0."
                               "pma_full_upstream_ga_v1_20261013.harbor_adapter:HarborGenericAgent"),
                   "--model", "claude-opus-4-8", "--mounts", json.dumps(mounts),
                   "--extra-docker-compose", str(root / "bundle" / "isolation.compose.json"),
                   "--n-concurrent", "1", "--max-retries", "0", "--yes",
                   "--disable-verification", "--agent-timeout-multiplier",
                   format(args.timeout_sec / 900, ".15g")]
        kwargs = {"llm_no": 0, "run_id": args.run_id, "task_id": args.task,
                  "expected_model": "claude-opus-4-8", "python_home": args.python_home,
                  "ga_source_sha256": record["ga_bundle_tree_sha256"],
                  "timeout_sec": args.timeout_sec, "max_turns": 2,
                  "llm_config_name": args.task_profile, "condition_id": "pma-neutral"}
        for key, value in kwargs.items():
            command += ["--ak", f"{key}={value}"]
        env = dict(os.environ)
        repo = STAGE.parents[2]
        env["PYTHONPATH"] = os.pathsep.join((str(repo), str(repo / "GenericAgent-main"),
                                            str(Path(args.bench_root).resolve(strict=True))))
        env["GA_RUN_ISOLATION"] = "no-network-unix-inference-v1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["NO_COLOR"] = "1"
        env["CI"] = "1"
        env["GA_PMA_UPSTREAM_ENABLED"] = "1" if args.condition == "B" else "0"
        env["GA_PMA_ENABLED"] = env["GA_MONITOR_ENABLED"] = "0"
        env["GA_M0_MONITOR_ENABLED"] = "0"
        if args.condition == "B":
            env.update(GA_PMA_UPSTREAM_REQUESTS="/run/pma-bridge/requests",
                       GA_PMA_UPSTREAM_RESPONSES="/run/pma-bridge/responses",
                       GA_PMA_UPSTREAM_DEADLINE_EPOCH=str(deadline))
        (root / "archive" / "offline_command.json").write_text(json.dumps({
            "argv": command, "public_env": {key: env[key] for key in (
                "GA_RUN_ISOLATION", "GA_PMA_UPSTREAM_ENABLED", "GA_PMA_ENABLED",
                "GA_MONITOR_ENABLED")}}, indent=2), encoding="utf-8")
        with (root / "archive" / "harbor.stdout.log").open("wb") as out, (
                root / "archive" / "harbor.stderr.log").open("wb") as err:
            harbor = subprocess.Popen(command, cwd=repo, env=env, stdout=out, stderr=err)
            mounts = []
            try:
                while harbor.poll() is None:
                    if time.time() >= deadline:
                        raise subprocess.TimeoutExpired(command, args.timeout_sec)
                    current_mounts = capture_mounts(root)
                    if len(current_mounts) > len(mounts):
                        mounts = current_mounts
                        if mounts:
                            (root / "archive" / "actual_container_mounts.json").write_text(
                                json.dumps(mounts, indent=2), encoding="utf-8")
                    time.sleep(.5)
                result = harbor
            finally:
                if harbor.poll() is None:
                    try:
                        harbor.kill()
                        harbor.wait(timeout=10)
                    except BaseException as exc:
                        cleanup_errors.append(f"harbor_stop_unknown:{type(exc).__name__}:{exc}")
        complete_mounts = capture_mounts(root, include_stopped=True)
        if len(complete_mounts) > len(mounts):
            mounts = complete_mounts
            (root / "archive" / "actual_container_mounts.json").write_text(
                json.dumps(mounts, indent=2), encoding="utf-8")
    except BaseException as exc:
        primary_failure = {"type": type(exc).__name__, "message": str(exc)}
    finally:
        if worker is not None:
            if worker.poll() is None:
                try:
                    (root / "host_private" / "stop.request").touch()
                    worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        worker.kill()
                        worker.wait(timeout=5)
                    except BaseException as exc:
                        cleanup_errors.append(f"worker_stop_unknown:{type(exc).__name__}:{exc}")
                except BaseException as exc:
                    cleanup_errors.append(f"worker_stop_unknown:{type(exc).__name__}:{exc}")
            if worker.poll() is None:
                cleanup_errors.append("worker_still_running")
            if worker_stdout is not None:
                worker_stdout.close()
            if worker_stderr is not None:
                worker_stderr.close()
    worker_exit = root / "host_private" / "worker_exit.json"
    mount_file = root / "archive" / "actual_container_mounts.json"
    try:
        actual_mounts = json.loads(mount_file.read_text(encoding="utf-8")) if mount_file.is_file() else []
    except BaseException as exc:
        cleanup_errors.append(f"mount_record_unreadable:{type(exc).__name__}:{exc}")
        actual_mounts = []
    exposed_private = any(str(root / "host_private") in str(row.get("mounts"))
                          for row in actual_mounts)
    try:
        cleanup_errors.extend(clean_owned_containers(root))
        remaining_containers = capture_mounts(root, include_stopped=True)
    except BaseException as exc:
        cleanup_errors.append(f"container_cleanup_unknown:{type(exc).__name__}:{exc}")
        remaining_containers = None
    try:
        worker_receipt = (json.loads(worker_exit.read_text(encoding="utf-8"))
                          if worker_exit.is_file() else None)
    except BaseException as exc:
        cleanup_errors.append(f"worker_receipt_unreadable:{type(exc).__name__}:{exc}")
        worker_receipt = None
    main = [row for row in actual_mounts if row["image_id"] == record["image_id"]]
    spool_ok = args.condition == "A" or (len(main) == 1 and
        {m["destination"]: m["rw"] for m in main[0]["mounts"]}.get(
            "/run/pma-bridge/requests") is True and
        {m["destination"]: m["rw"] for m in main[0]["mounts"]}.get(
            "/run/pma-bridge/responses") is False)
    integration_ok = bool(primary_failure is None and result is not None and result.returncode == 0 and
        not exposed_private and not remaining_containers and not cleanup_errors and
        len(main) == 1 and spool_ok and
        (args.condition == "A" or (worker.returncode == 0 and worker_receipt is not None
         and worker_receipt.get("task_end_saved") is True)))
    status = {**record, "harbor_return_code": None if result is None else result.returncode,
              "worker_return_code": None if worker is None else worker.returncode,
              "worker_private_mounted": exposed_private if actual_mounts else "unknown",
              "actual_container_count": len(actual_mounts),
              "remaining_owned_containers": (None if remaining_containers is None else
                                             [row["id"] for row in remaining_containers]),
              "cleanup_errors": cleanup_errors,
              "primary_failure": primary_failure,
              "cleanup_confirmed": remaining_containers == [] and not cleanup_errors
              and (worker is None or worker.poll() is not None),
              "spool_mounts_verified": spool_ok, "integration_ok": integration_ok,
              "worker_exit_receipt": worker_receipt}
    (root / "archive" / "offline_result.json").write_text(
        json.dumps(status, indent=2), encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=TASKS, required=True)
    parser.add_argument("--condition", choices=("A", "B"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--ga-source", required=True)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--task-profile-file", required=True)
    parser.add_argument("--task-profile", default="native_claude_cc_vibe_opus48")
    parser.add_argument("--python-home", default="cpython-3.12.12-linux-x86_64-gnu")
    parser.add_argument("--worker-python", required=True)
    parser.add_argument("--harbor-exe", required=True)
    parser.add_argument("--bench-root", required=True)
    parser.add_argument("--timeout-sec", type=int, default=180)
    parser.add_argument("--execution-authorized", action="store_true")
    parser.add_argument("--multiturn-fixture", action="store_true")
    args = parser.parse_args()
    result = run_offline(args)
    print(json.dumps(result, indent=2))
    if not result["integration_ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
