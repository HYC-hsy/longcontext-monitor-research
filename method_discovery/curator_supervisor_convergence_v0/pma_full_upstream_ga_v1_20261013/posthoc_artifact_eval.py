"""One-use, artifact-only native evaluator for the four frozen retry products.

No GA, PMA, provider, or Harbor agent process is created here.  The original
task test.sh runs in a disposable official-image container after /app is
replaced by a no-copy volume restored from the registered frozen tar.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time

sys.path.insert(0, "E:/LongContext")
from long_context_bench.scripts.isolated_run_bundle import digest_tree


STAGE = Path(__file__).resolve().parent
ARCHIVE = STAGE / "live_batch_retry_20261014"
POSTHOC = STAGE / "posthoc_20261014"
MANIFEST = STAGE / "FOUR_RUN_MANIFEST_OPUS48_RETRY_20261014.json"
ORDER = (("db_a", "db-wal-recovery"), ("db_b", "db-wal-recovery"),
         ("code_b", "fix-code-vulnerability"),
         ("code_a", "fix-code-vulnerability"))
REGISTERED_TARS = {
    "db_a": "3a6796614f3852190a2de3fb2866e43ee3b04ef398e3427e97dfe4f045e68cde",
    "db_b": "9e0f0eb4d1a1e925385cd6ceef2688a542cdf6e222933ddc7303b3d7c78da88b",
    "code_b": "ae7b2326db6f3bc316836a2dca210c7e91f67ca24624e3b95ca7ae2352ff9530",
    "code_a": "9331ee3f62180cb3eaf20d9a8834a60ddce634d8c3848a87d688252a5b13fa3b",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def store(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def command(argv: list[str], directory: Path, name: str, *, timeout: int = 900,
            stdin: bytes | None = None) -> subprocess.CompletedProcess:
    start = time.time()
    try:
        completed = subprocess.run(argv, input=stdin, capture_output=True, timeout=timeout)
        outcome = {"argv": argv, "started_epoch": start, "ended_epoch": time.time(),
                   "returncode": completed.returncode, "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(argv, None, exc.stdout or b"", exc.stderr or b"")
        outcome = {"argv": argv, "started_epoch": start, "ended_epoch": time.time(),
                   "returncode": None, "timed_out": True}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.stdout").write_bytes(completed.stdout)
    (directory / f"{name}.stderr").write_bytes(completed.stderr)
    store(directory / f"{name}.json", outcome)
    return completed


def require_success(result: subprocess.CompletedProcess, name: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"{name} failed or timed out: {result.returncode}")


def tar_members(raw: bytes) -> dict[str, dict]:
    items = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            name = member.name.removeprefix("./").rstrip("/")
            if not name or name == ".":
                continue
            if (name.startswith("/") or ".." in Path(name).parts or
                    not (member.isfile() or member.isdir()) or name in items):
                raise RuntimeError(f"unsafe or repeated tar member: {name}")
            content = archive.extractfile(member).read() if member.isfile() else b""
            items[name] = {"kind": "file" if member.isfile() else "directory",
                           "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                           "mode": member.mode & 0o777}
    return items


def validate_source() -> dict:
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))
    identities = {}
    for arm, task in ORDER:
        root = ARCHIVE / "raw" / "arms" / arm
        recorded = json.loads((root / "archive" / "agent_end_frozen.json")
                              .read_text(encoding="utf-8"))
        product = root / "archive" / "pre_evaluation_app.tar"
        expected = REGISTERED_TARS[arm]
        if (not recorded.get("writers_stopped") or not recorded.get("sidecar_clean") or
                recorded.get("tar_sha256") != expected or sha(product) != expected or
                product.stat().st_size != recorded.get("tar_bytes")):
            raise RuntimeError(f"frozen product or writer identity mismatch: {arm}")
        tests = STAGE / "assets" / "evaluator" / task / "tests"
        spec = frozen["assets"][task]
        if (digest_tree(tests) != spec["native_tests_tree_sha256"] or
                sha(tests / "test.sh") != spec["native_test_sh_sha256"]):
            raise RuntimeError(f"official evaluator identity mismatch: {task}")
        image = spec["repo_digest"]
        inspected = command(["docker", "image", "inspect", image], POSTHOC / "identity",
                            f"image_{task}", timeout=60)
        require_success(inspected, "docker image inspect")
        actual = json.loads(inspected.stdout)[0]
        if (actual["Id"] != spec["image_id"] or image not in actual["RepoDigests"] or
                (actual["Os"] + "/" + actual["Architecture"]) != spec["platform"]):
            raise RuntimeError(f"official image identity mismatch: {task}")
        members = tar_members(product.read_bytes())
        identities[arm] = {"task": task, "tar_sha256": expected,
                           "tar_bytes": product.stat().st_size,
                           "file_manifest": members, "official_image_id": actual["Id"],
                           "official_repo_digest": image,
                           "evaluator_tree_sha256": spec["native_tests_tree_sha256"]}
    return identities


def preflight() -> None:
    if POSTHOC.exists():
        raise FileExistsError(POSTHOC)
    POSTHOC.mkdir()
    identities = validate_source()
    store(POSTHOC / "INPUT_IDENTITIES.json", identities)
    scripts = {
        "db-wal-recovery": (
            "set -eu; apt-get update; apt-get install -y curl; "
            "curl -LsSf https://astral.sh/uv/0.9.5/install.sh -o /tmp/install-uv.sh; "
            "sh /tmp/install-uv.sh; . /root/.local/bin/env; "
            "uvx -p 3.13 -w pytest==8.4.1 -w pytest-json-ctrf==0.3.5 "
            "pytest --help | grep -- --ctrf"),
        "fix-code-vulnerability": (
            "set -eu; python -m pip install pytest==8.4.1 "
            "pytest-json-ctrf==0.3.5; python -m pytest --help | grep -- --ctrf"),
    }
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for task, script in scripts.items():
        image = manifest["assets"][task]["repo_digest"]
        result = command(["docker", "run", "--rm", "--network", "bridge",
                          "--user", "0", "--cpus", "1", "--memory", "2048m",
                          "--entrypoint", "sh", image, "-lc", script],
                         POSTHOC / "preflight", task, timeout=600)
        require_success(result, f"{task} dependency preflight")
    marker = {"dependency_preflight_complete": True, "candidate_products_mounted": False,
              "task_pma_provider_evaluator_calls": 0}
    store(POSTHOC / "PREFLIGHT_RESULT.json", marker)


def inspect_reports(task: str, logs: Path) -> tuple[bool, dict]:
    names = (["ctrf.json"] if task == "db-wal-recovery" else
             ["original-repo-ctrf.json", "ctrf.json"])
    summaries = {}
    for name in names:
        path = logs / name
        if not path.is_file():
            return False, {"missing_report": name}
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            results = report["results"]
            tests = results["tests"]
            count = int(results["summary"]["tests"])
            if count < 1 or len(tests) < 1 or count != len(tests):
                return False, {"incomplete_report": name, "declared": count,
                               "observed": len(tests)}
            statuses = [item.get("status") for item in tests]
            if any(status not in ("passed", "failed", "skipped") for status in statuses):
                return False, {"unknown_test_status": name, "statuses": statuses}
            summaries[name] = {"tests": count, "statuses": statuses}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return False, {"invalid_report": name, "error": type(exc).__name__}
    return True, summaries


def evaluate_one(arm: str, identity: dict) -> dict:
    task = identity["task"]
    root = POSTHOC / arm
    if root.exists():
        raise FileExistsError(root)
    root.mkdir()
    logs = root / "verifier"
    logs.mkdir()
    volume = f"pma_posthoc_20261014_{arm}"
    container = f"pma_posthoc_20261014_{arm}"
    image = identity["official_repo_digest"]
    tests = STAGE / "assets" / "evaluator" / task / "tests"
    product = ARCHIVE / "raw" / "arms" / arm / "archive" / "pre_evaluation_app.tar"
    result = {"arm": arm, "task": task, "input_tar_sha256": identity["tar_sha256"],
              "evaluator_started": False, "reward": None, "interpretability": "unknown",
              "cleanup_confirmed": False, "errors": []}
    volume_created = container_created = False
    try:
        require_success(command(["docker", "volume", "create", volume], root,
                                "volume_create", timeout=60), "volume create")
        volume_created = True
        create = ["docker", "create", "--name", container, "--network", "bridge",
                  "--user", "0", "--cpus", "1", "--memory", "2048m",
                  "--mount", f"type=volume,source={volume},target=/app,volume-nocopy",
                  "--mount", f"type=bind,source={tests.resolve()},target=/tests,readonly",
                  "--mount", f"type=bind,source={logs.resolve()},target=/logs/verifier",
                  "--workdir", "/app", "--entrypoint", "sleep", image, "infinity"]
        require_success(command(create, root, "container_create", timeout=60),
                        "container create")
        container_created = True
        require_success(command(["docker", "start", container], root,
                                "container_start", timeout=60), "container start")
        empty = command(["docker", "exec", container, "sh", "-lc",
                         "test -z \"$(find /app -mindepth 1 -print -quit)\""],
                        root, "app_empty", timeout=30)
        require_success(empty, "no-copy /app empty verification")
        require_success(command(["docker", "cp", "-", f"{container}:/app"], root,
                                "restore", timeout=90, stdin=product.read_bytes()),
                        "frozen tar restore")
        before = command(["docker", "cp", f"{container}:/app/.", "-"], root,
                         "pre_eval_capture", timeout=90)
        require_success(before, "restored /app capture")
        (root / "pre_eval_app.tar").write_bytes(before.stdout)
        restored = tar_members(before.stdout)
        if restored != identity["file_manifest"]:
            store(root / "restore_difference.json", {"expected": identity["file_manifest"],
                                                   "actual": restored})
            raise RuntimeError("restored /app differs from frozen source")
        if task == "fix-code-vulnerability":
            probe = command(["docker", "exec", "-w", "/app", container, "python", "-c",
                             "import importlib.util; s=importlib.util.find_spec('bottle'); "
                             "print(s.origin if s else 'missing')"], root,
                            "bottle_import_path", timeout=30)
            require_success(probe, "bottle import path probe")
            if probe.stdout.decode("utf-8", "replace").strip() != "/app/bottle.py":
                raise RuntimeError("bottle import does not resolve to this arm's /app")
        inspect = command(["docker", "inspect", container], root,
                          "evaluation_container_identity", timeout=60)
        require_success(inspect, "evaluation container inspect")
        raw = json.loads(inspect.stdout)[0]
        mounts = {mount["Destination"]: mount for mount in raw["Mounts"]}
        if (raw["Image"] != identity["official_image_id"] or
                mounts["/app"]["Type"] != "volume" or
                mounts["/app"]["Name"] != volume or
                mounts["/tests"]["RW"] or
                raw["HostConfig"]["NetworkMode"] != "bridge"):
            raise RuntimeError("evaluation image, mount, or network identity mismatch")
        store(root / "evaluation_identity.json", {"image_id": raw["Image"],
              "network_mode": raw["HostConfig"]["NetworkMode"],
              "mounts": [{key: m.get(key) for key in ("Destination", "Type", "Name", "RW")}
                         for m in raw["Mounts"]]})
        store(root / "attempt_started.json", {"arm": arm, "started_epoch": time.time(),
              "command": ["docker", "exec", "-w", "/app", container,
                          "bash", "/tests/test.sh"], "single_native_invocation": True})
        result["evaluator_started"] = True
        evaluation = command(["docker", "exec", "-w", "/app", container,
                              "bash", "/tests/test.sh"], root, "native_evaluator",
                             timeout=900)
        reward_path = logs / "reward.txt"
        result["reward"] = reward_path.read_text(encoding="utf-8").strip() if reward_path.exists() else None
        complete, reports = inspect_reports(task, logs)
        result["test_reports"] = reports
        result["evaluator_exit"] = evaluation.returncode
        result["interpretability"] = (
            "candidate_result" if complete and result["reward"] in ("0", "1") and
            evaluation.returncode is not None else "infrastructure_or_incomplete")
        after = command(["docker", "cp", f"{container}:/app/.", "-"], root,
                        "post_eval_capture", timeout=90)
        require_success(after, "post-evaluation /app capture")
        (root / "post_eval_app.tar").write_bytes(after.stdout)
        result["post_eval_app_sha256"] = sha(root / "post_eval_app.tar")
    except BaseException as exc:
        result["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        result["interpretability"] = "infrastructure_or_incomplete"
    finally:
        cleanup_ok = True
        if container_created:
            cleanup_ok &= command(["docker", "rm", "-f", container], root,
                                  "container_remove", timeout=60).returncode == 0
        if volume_created:
            cleanup_ok &= command(["docker", "volume", "rm", volume], root,
                                  "volume_remove", timeout=60).returncode == 0
        check = command(["docker", "ps", "-a", "--filter", f"name=^{container}$",
                         "--format", "{{.ID}}"], root, "cleanup_verify_container", timeout=30)
        volume_check = command(["docker", "volume", "ls", "-q", "--filter",
                                f"name=^{volume}$"], root, "cleanup_verify_volume", timeout=30)
        result["cleanup_confirmed"] = (cleanup_ok and check.returncode == 0 and
                                         volume_check.returncode == 0 and
                                         not check.stdout.strip() and not volume_check.stdout.strip())
        if not result["cleanup_confirmed"]:
            result["errors"].append({"type": "CleanupUnknown", "message": "owned resource removal unconfirmed"})
        store(root / "RESULT.json", result)
    return result


def evaluate() -> None:
    if not json.loads((POSTHOC / "PREFLIGHT_RESULT.json").read_text(encoding="utf-8"))[
            "dependency_preflight_complete"]:
        raise RuntimeError("dependency preflight incomplete")
    identities = validate_source()
    previous = POSTHOC / "RESULT_TABLE.json"
    if previous.exists():
        raise FileExistsError(previous)
    table = {"schema": "reconstructed-posthoc-artifact-evaluation-v1", "arms": [],
             "not_started": [], "stop_reason": None}
    for index, (arm, _) in enumerate(ORDER):
        outcome = evaluate_one(arm, identities[arm])
        table["arms"].append(outcome)
        store(previous, table)
        if not outcome["cleanup_confirmed"] or outcome["interpretability"] != "candidate_result":
            table["stop_reason"] = "cleanup_unknown" if not outcome["cleanup_confirmed"] else \
                                   "evaluation_infrastructure_or_incomplete"
            table["not_started"] = [item[0] for item in ORDER[index + 1:]]
            break
    store(previous, table)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "evaluate"))
    args = parser.parse_args()
    if args.mode == "preflight":
        preflight()
    else:
        evaluate()


if __name__ == "__main__":
    main()
