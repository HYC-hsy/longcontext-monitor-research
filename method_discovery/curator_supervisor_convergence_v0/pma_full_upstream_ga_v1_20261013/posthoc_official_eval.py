"""Single-use, official-blob posthoc evaluator for four immutable artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from .posthoc_artifact_eval import (ARCHIVE, MANIFEST, ORDER, REGISTERED_TARS,
                                    command, inspect_reports, sha, store, tar_members)


STAGE = Path(__file__).resolve().parent / "posthoc_official_20261014"
RUNS = STAGE / "runs_v2"
SLOT = {"db_a": 1, "db_b": 2, "code_b": 3, "code_a": 4}
OFFICIAL_SH = {
    "db-wal-recovery": "4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334",
    "fix-code-vulnerability": "f1611da693cb4cfc5e8482698c6a1858a5c67220ae9db89b50aed66584e9b17f",
}


def require(result: subprocess.CompletedProcess, stage: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"{stage}: exit={result.returncode}")


def validate_inputs(identity_dir: Path) -> dict:
    original = json.loads(MANIFEST.read_text(encoding="utf-8"))
    provenance = json.loads((STAGE / "PROVENANCE_AMENDMENT.json").read_text(encoding="utf-8"))
    authorization = json.loads((STAGE / "AUTHORIZATION_SCOPE.json").read_text(encoding="utf-8"))
    if (authorization["original_archive_commit"] != "b1fe2a5a252fb3d5f7c426ffdcee14f5283069fb" or
            authorization["official_source_commit"] != provenance["commit"] or
            authorization["task_pma_provider_training_scoring_model_authorized"] is not False or
            authorization["native_evaluator_max_starts_per_arm"] != 1 or
            authorization["evaluation_order"] != [
                {"arm": arm, "tar_sha256": REGISTERED_TARS[arm]} for arm, _ in ORDER]):
        raise RuntimeError("posthoc authorization scope or order mismatch")
    if provenance["commit"] != original["official_task_commit"]:
        raise RuntimeError("upstream evaluator commit mismatch")
    members = {item["path"]: item for item in provenance["members"]}
    result = {}
    for arm, task in ORDER:
        source = ARCHIVE / "raw" / "arms" / arm
        product = source / "archive" / "pre_evaluation_app.tar"
        frozen = json.loads((source / "archive" / "agent_end_frozen.json").read_text(encoding="utf-8"))
        expected = REGISTERED_TARS[arm]
        if (not frozen.get("writers_stopped") or not frozen.get("sidecar_clean") or
                frozen.get("tar_sha256") != expected or sha(product) != expected or
                frozen.get("tar_bytes") != product.stat().st_size):
            raise RuntimeError(f"frozen artifact identity or stop proof differs: {arm}")
        tests = STAGE / task / "tests"
        expected_files = {name.removeprefix(task + "/tests/"): item for name, item in members.items()
                          if name.startswith(task + "/tests/")}
        found = {item.relative_to(tests).as_posix() for item in tests.rglob("*") if item.is_file()}
        if found != set(expected_files) or not expected_files:
            raise RuntimeError(f"official evaluator file set mismatch: {task}")
        for filename, identity in expected_files.items():
            path = tests / filename
            if sha(path) != identity["sha256"] or path.stat().st_size != identity["bytes"]:
                raise RuntimeError(f"official evaluator byte mismatch: {task}/{filename}")
        shell = tests / "test.sh"
        if (sha(shell) != OFFICIAL_SH[task] or b"\r\n" in shell.read_bytes() or
                shell.read_bytes().startswith(b"\xef\xbb\xbf")):
            raise RuntimeError(f"official shell script differs or has CRLF/BOM: {task}")
        image = original["assets"][task]["repo_digest"]
        inspect = command(["docker", "image", "inspect", image], identity_dir,
                          f"image_{task}", timeout=60)
        require(inspect, "image inspect")
        actual = json.loads(inspect.stdout)[0]
        if (actual["Id"] != original["assets"][task]["image_id"] or
                image not in actual["RepoDigests"] or
                actual["Os"] + "/" + actual["Architecture"] != original["assets"][task]["platform"]):
            raise RuntimeError(f"fixed Docker image identity mismatch: {task}")
        result[arm] = {"task": task, "image_id": actual["Id"], "repo_digest": image,
                       "tar_sha256": expected, "tar_bytes": product.stat().st_size,
                       "file_manifest": tar_members(product.read_bytes()),
                       "evaluator_members": expected_files}
    return result


def make_container(root: Path, name: str, image: str, tests: Path, logs: Path) -> tuple[str, str]:
    volume = "pma_posthoc_official_20261014_" + name
    container = volume
    require(command(["docker", "volume", "create", volume], root,
                    "volume_create", timeout=60), "volume create")
    args = ["docker", "create", "--name", container, "--network", "bridge",
            "--user", "0", "--cpus", "1", "--memory", "2048m",
            "--mount", f"type=volume,source={volume},target=/app,volume-nocopy",
            "--mount", f"type=bind,source={tests.resolve()},target=/tests,readonly",
            "--mount", f"type=bind,source={logs.resolve()},target=/logs/verifier",
            "--workdir", "/app", "--entrypoint", "sleep", image, "infinity"]
    require(command(args, root, "container_create", timeout=60), "container create")
    require(command(["docker", "start", container], root, "container_start", timeout=60),
            "container start")
    return container, volume


def cleanup(root: Path, container: str, volume: str) -> bool:
    command(["docker", "rm", "-f", container], root,
            "container_remove", timeout=60)
    command(["docker", "volume", "rm", volume], root,
            "volume_remove", timeout=60)
    c = command(["docker", "ps", "-a", "--filter", f"name=^{container}$",
                 "--format", "{{.ID}}"], root, "container_verify", timeout=30)
    v = command(["docker", "volume", "ls", "-q", "--filter", f"name=^{volume}$"],
                root, "volume_verify", timeout=30)
    return (c.returncode == v.returncode == 0 and
            not c.stdout.strip() and not v.stdout.strip())


def verify_container(root: Path, container: str, volume: str, identity: dict) -> None:
    raw = command(["docker", "inspect", container], root, "container_identity", timeout=60)
    require(raw, "container inspect")
    inspected = json.loads(raw.stdout)[0]
    mounts = {item["Destination"]: item for item in inspected["Mounts"]}
    if (inspected["Image"] != identity["image_id"] or
            inspected["HostConfig"]["NetworkMode"] != "bridge" or
            mounts["/app"]["Name"] != volume or mounts["/app"]["Type"] != "volume" or
            mounts["/tests"]["RW"] or mounts["/logs/verifier"]["RW"] is not True):
        raise RuntimeError("actual evaluation container identity or mount mismatch")
    store(root / "verified_mounts.json", {"image_id": inspected["Image"],
          "network": inspected["HostConfig"]["NetworkMode"],
          "mounts": [{key: item.get(key) for key in ("Destination", "Source", "Name", "Type", "RW")}
                     for item in inspected["Mounts"]]})
    empty = command(["docker", "exec", container, "sh", "-lc",
                     'test -z "$(find /app -mindepth 1 -print -quit)"'],
                    root, "app_empty", timeout=30)
    require(empty, "no-copy /app emptiness")
    names = command(["docker", "exec", container, "find", "/tests", "-type", "f",
                     "-printf", "%P\n"], root, "tests_names", timeout=30)
    require(names, "container evaluator file listing")
    actual_names = set(names.stdout.decode().splitlines())
    if actual_names != set(identity["evaluator_members"]):
        raise RuntimeError("container /tests file set differs from official blobs")
    observed = {}
    for name, expected in identity["evaluator_members"].items():
        measured = command(["docker", "exec", container, "sha256sum", "/tests/" + name],
                           root, "test_hash_" + name.replace(".", "_"), timeout=30)
        require(measured, "container evaluator byte hash")
        digest = measured.stdout.decode().split()[0]
        if digest != expected["sha256"]:
            raise RuntimeError(f"container evaluator byte mismatch: {name}")
        observed[name] = digest
    store(root / "container_tests_readback.json", observed)
    syntax = command(["docker", "exec", "-w", "/app", container,
                      "bash", "-n", "/tests/test.sh"], root, "bash_syntax", timeout=30)
    require(syntax, "official shell syntax")


def run_preflight(task: str, identity: dict) -> bool:
    root = RUNS / "preflight" / task
    root.mkdir(parents=True)
    logs = root / "verifier"
    logs.mkdir()
    tests = STAGE / task / "tests"
    name = "preflight_" + task.replace("-", "_")
    container = volume = "pma_posthoc_official_20261014_" + name
    errors = []
    try:
        container, volume = make_container(root, name, identity["repo_digest"], tests, logs)
        verify_container(root, container, volume, identity)
        if task == "db-wal-recovery":
            script = ("set -euo pipefail; apt-get update; apt-get install -y curl; "
                      "command -v curl; curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh; "
                      "source /root/.local/bin/env; command -v uvx; "
                      "uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 "
                      "python -c 'import ast,pathlib; ast.parse(pathlib.Path(\"/tests/test_outputs.py\").read_bytes())'; "
                      "uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 "
                      "pytest --help | grep -- --ctrf")
        else:
            script = ("set -euo pipefail; command -v pip; command -v python; "
                      "pip install pytest==8.4.1 pytest-json-ctrf==0.3.5; "
                      "pip --version; python -m pytest --version; "
                      "python -c 'import ast,pathlib; ast.parse(pathlib.Path(\"/tests/test_outputs.py\").read_bytes())'; "
                      "python -m pytest --help | grep -- --ctrf")
        result = command(["docker", "exec", "-w", "/app", container,
                          "bash", "-lc", script], root, "dependency_check", timeout=600)
        require(result, "official dependency commands and Python syntax")
        writable = command(["docker", "exec", container, "sh", "-lc",
                            "test -w /logs/verifier && test -z \"$(find /logs/verifier -mindepth 1 -print -quit)\""],
                           root, "logs_writable", timeout=30)
        require(writable, "verifier output directory")
    except BaseException as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc)})
    clean = cleanup(root, container, volume)
    store(root / "RESULT.json", {"passed": not errors and clean,
                                  "cleanup_confirmed": clean, "errors": errors,
                                  "candidate_mounted": False})
    return not errors and clean


def preflight() -> bool:
    if RUNS.exists():
        raise FileExistsError(RUNS)
    RUNS.mkdir()
    identities = validate_inputs(RUNS / "identity_preflight")
    store(RUNS / "INPUT_IDENTITIES.json", identities)
    table = {"schema": "official-posthoc-preflight-v1", "tasks": {},
             "candidate_evaluator_calls": 0, "stopped": False}
    for task in ("db-wal-recovery", "fix-code-vulnerability"):
        arm = next(arm for arm, item in ORDER if item == task)
        passed = run_preflight(task, identities[arm])
        table["tasks"][task] = {"passed": passed}
        if not passed:
            table["stopped"] = True
            break
    store(RUNS / "PREFLIGHT_RESULT.json", table)
    return not table["stopped"]


def evaluate_one(arm: str, identity: dict) -> dict:
    root = RUNS / arm
    if root.exists():
        raise FileExistsError(root)
    root.mkdir()
    logs = root / "verifier"
    logs.mkdir()
    task = identity["task"]
    tests = STAGE / task / "tests"
    name = arm
    container = volume = "pma_posthoc_official_20261014_" + name
    product = ARCHIVE / "raw" / "arms" / arm / "archive" / "pre_evaluation_app.tar"
    result = {"arm": arm, "order": SLOT[arm], "task": task,
              "classification": "unknown", "evaluator_started": False,
              "input_tar_sha256": identity["tar_sha256"], "reward": None,
              "cleanup_confirmed": False, "errors": []}
    try:
        container, volume = make_container(root, name, identity["repo_digest"], tests, logs)
        verify_container(root, container, volume, identity)
        restored = command(["docker", "cp", "-", f"{container}:/app"], root,
                           "restore", timeout=90, stdin=product.read_bytes())
        require(restored, "frozen artifact restore")
        snapshot = command(["docker", "cp", f"{container}:/app/.", "-"], root,
                           "pre_eval_capture", timeout=90)
        require(snapshot, "pre-evaluation artifact capture")
        (root / "pre_eval_app.tar").write_bytes(snapshot.stdout)
        if tar_members(snapshot.stdout) != identity["file_manifest"]:
            raise RuntimeError("restored /app differs from precise frozen artifact")
        if task == "fix-code-vulnerability":
            probe = command(["docker", "exec", "-w", "/app", container, "python", "-c",
                             "import importlib.util; x=importlib.util.find_spec('bottle'); print(x.origin if x else 'missing')"],
                            root, "bottle_import", timeout=30)
            require(probe, "candidate import-path check")
            if probe.stdout.decode().strip() != "/app/bottle.py":
                raise RuntimeError("candidate bottle import does not originate in restored /app")
        store(root / "attempt_started.json", {"command": ["docker", "exec", "-w", "/app",
              container, "bash", "/tests/test.sh"], "start_epoch": time.time(),
              "single_official_native_evaluation": True})
        result["evaluator_started"] = True
        native = command(["docker", "exec", "-w", "/app", container,
                          "bash", "/tests/test.sh"], root, "native_evaluator", timeout=900)
        result["native_exit"] = native.returncode
        result["native_timeout"] = native.returncode is None
        reward = logs / "reward.txt"
        result["reward"] = reward.read_text(encoding="utf-8").strip() if reward.exists() else None
        complete, reports = inspect_reports(task, logs)
        result["test_reports"] = reports
        if complete and result["reward"] in ("0", "1") and native.returncode is not None:
            result["classification"] = "candidate_result"
        else:
            result["classification"] = "evaluation_infrastructure_or_incomplete"
        final = command(["docker", "cp", f"{container}:/app/.", "-"], root,
                        "post_eval_capture", timeout=90)
        require(final, "post-evaluation artifact capture")
        (root / "post_eval_app.tar").write_bytes(final.stdout)
        result["post_eval_app_sha256"] = sha(root / "post_eval_app.tar")
    except BaseException as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        result["classification"] = "evaluation_infrastructure_or_incomplete"
    finally:
        result["cleanup_confirmed"] = cleanup(root, container, volume)
        if not result["cleanup_confirmed"]:
            result["errors"].append({"type": "CleanupUnknown"})
        store(root / "RESULT.json", result)
    return result


def evaluate() -> bool:
    marker = json.loads((RUNS / "PREFLIGHT_RESULT.json").read_text(encoding="utf-8"))
    if marker["stopped"] or set(marker["tasks"]) != {
            "db-wal-recovery", "fix-code-vulnerability"} or not all(
                item["passed"] for item in marker["tasks"].values()):
        raise RuntimeError("both empty-/app official evaluator preflights must pass")
    identities = validate_inputs(RUNS / "identity_evaluation")
    table_path = RUNS / "RESULT_TABLE.json"
    if table_path.exists():
        raise FileExistsError(table_path)
    table = {"schema": "reconstructed-posthoc-official-blobs-v1", "arms": [],
             "not_started": [], "stop_reason": None}
    for index, (arm, _) in enumerate(ORDER):
        item = evaluate_one(arm, identities[arm])
        table["arms"].append(item)
        if item["classification"] != "candidate_result" or not item["cleanup_confirmed"]:
            table["stop_reason"] = ("cleanup_unknown" if not item["cleanup_confirmed"] else
                                     "evaluation_infrastructure_or_incomplete")
            table["not_started"] = [later for later, _ in ORDER[index + 1:]]
            store(table_path, table)
            return False
        store(table_path, table)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "evaluate"))
    mode = parser.parse_args().mode
    passed = preflight() if mode == "preflight" else evaluate()
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
