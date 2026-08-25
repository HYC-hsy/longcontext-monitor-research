"""M4 runner for one native Harbor/Terminal-Bench 2 task."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import base64
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TB_ROOT = Path(os.environ.get("TB2_ROOT", r"E:\LongContext\Ref_Benchmark\Terminal-Bench"))
TASK_ID = "fix-code-vulnerability"
TASK_ROOT = TB_ROOT / TASK_ID
TB_COMMIT = "2fd12b88aafdd04a52c298e3940bcb189f9766d6"
GA_ROOT = Path(os.environ.get("GA_HOST_ROOT", r"E:\LongContext\GenericAgent-main"))
GA_SOURCE_SHA256 = "1bb8f385ee0b1d1568a90c00aeda4f2690bebfc7a658afa17a243d028063bb84"
RUNTIME_ROOT = Path(os.environ.get("M4_RUNTIME_ROOT", r"E:\LongContext\bench_runtime\m4"))
GA_RUNTIME = Path(os.environ.get("GA_RUNTIME_ROOT", r"E:\LongContext\bench_runtime\m2\linux"))
HARBOR_ROOT = RUNTIME_ROOT / "harbor-src"
HARBOR_COMMIT = "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc"
HARBOR_EXE = RUNTIME_ROOT / "harbor-env" / "Scripts" / "harbor.exe"
WORK_ROOT = ROOT / "output" / "m4_harbor_tb2"
JOBS_ROOT = WORK_ROOT / "jobs"
RUNS_ROOT = WORK_ROOT / "runs"
OTEL_ROOT = WORK_ROOT / "otel"
COLLECTOR_NAME = "m4-otel-collector"
COLLECTOR_IMAGE = "otel/opentelemetry-collector-contrib:0.130.1"
COLLECTOR_PORT = 14319
COLLECTOR_OUTPUT_LABEL = "longcontext.otel.output-sha256"
IMAGE_TAG = "alexgshaw/fix-code-vulnerability:20251031"
IMAGE_ID = "sha256:cac325252991f823713b2d0441502972901dd782bd67f66c03d9b1e410dac5c0"
IMAGE_REF = f"alexgshaw/fix-code-vulnerability@{IMAGE_ID}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], timeout: int = 600, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True,
                          encoding="utf-8", timeout=timeout, env=env)


def checked(cmd: list[str], timeout: int = 600, cwd: Path | None = None) -> str:
    result = run(cmd, timeout, cwd)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def git_identity(path: Path, expected: str) -> dict[str, Any]:
    if not (path / ".git").exists():
        raise RuntimeError(f"git checkout missing: {path}")
    base = ["git", "-c", f"safe.directory={path.resolve()}", "-C", str(path)]
    head = checked(base + ["rev-parse", "HEAD"])
    if head != expected:
        raise RuntimeError(f"commit mismatch for {path}: expected {expected}, got {head}")
    status_result = run(
        base + ["status", "--porcelain", "--untracked-files=all"], 60
    )
    if status_result.returncode:
        raise RuntimeError(
            f"failed to inspect Harbor checkout: {status_result.stderr.strip()}"
        )
    dirty = status_result.stdout.rstrip()
    if dirty:
        raise RuntimeError(f"checkout is dirty: {path}\n{dirty}")
    return {"path": str(path.resolve()), "commit": head, "clean": True}


def harbor_identity() -> dict[str, Any]:
    """Accept only the pinned clean checkout or the exact required M12 patches."""
    if not (HARBOR_ROOT / ".git").exists():
        raise RuntimeError(f"git checkout missing: {HARBOR_ROOT}")
    base = [
        "git",
        "-c",
        f"safe.directory={HARBOR_ROOT.resolve()}",
        "-C",
        str(HARBOR_ROOT),
    ]
    head = checked(base + ["rev-parse", "HEAD"])
    if head != HARBOR_COMMIT:
        raise RuntimeError(
            f"commit mismatch for {HARBOR_ROOT}: "
            f"expected {HARBOR_COMMIT}, got {head}"
        )
    status_result = run(
        base + ["status", "--porcelain", "--untracked-files=all"], 60
    )
    if status_result.returncode:
        raise RuntimeError(
            f"failed to inspect Harbor checkout: {status_result.stderr.strip()}"
        )
    dirty = status_result.stdout.rstrip()
    if not dirty:
        return {
            "path": str(HARBOR_ROOT.resolve()),
            "commit": head,
            "clean": True,
            "patches": {},
        }

    from scripts import prepare_harbor_lhtb_m12 as continuation
    from scripts import prepare_harbor_lhtb_structured_pass_m12 as structured
    from scripts import prepare_harbor_windows_sidecar_m12 as sidecar

    states = {
        "continuation": continuation.patch_state(HARBOR_ROOT),
        "windows_sidecar_crlf": sidecar.state(HARBOR_ROOT),
        "structured_pass": structured.state(HARBOR_ROOT),
    }
    expected_paths = {
        *continuation.PATCHED_PATHS,
        sidecar.PATCHED_PATH,
        structured.PATCHED_PATH,
    }
    actual_paths = {
        line[3:].replace("\\", "/")
        for line in dirty.splitlines()
        if len(line) >= 4
    }
    if set(states.values()) != {"applied"} or actual_paths != expected_paths:
        raise RuntimeError(
            f"Harbor checkout has unapproved changes: states={states}, "
            f"paths={sorted(actual_paths)}"
        )
    return {
        "path": str(HARBOR_ROOT.resolve()),
        "commit": head,
        "clean": False,
        "patches": {
            "states": states,
            "sha256": {
                "continuation": continuation.EXPECTED_PATCH_SHA256,
                "windows_sidecar_crlf": sidecar.EXPECTED_PATCH_SHA256,
                "structured_pass": structured.EXPECTED_PATCH_SHA256,
            },
        },
    }


def tree_hash(root: Path, *, ga_mode: bool = False) -> str:
    digest = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        excluded = {".git", "__pycache__", ".pytest_cache"}
        if any(part in excluded for part in rel.parts):
            continue
        # M4 copies this payload into the trial. Prompts, tool schemas, plugins,
        # and initial memory are behavioral inputs. The access counter is mutable
        # telemetry written by GA itself, not initial memory or source.
        ga_transient = {
            Path("memory") / "file_access_stats.json",
        }
        if ga_mode and ("temp" in rel.parts or rel in ga_transient):
            continue
        files.append(path)
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(4, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def python_home() -> Path:
    matches = sorted((GA_RUNTIME / "python").glob("cpython-3.12.*-linux-x86_64-gnu"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one GA Python runtime, found {len(matches)}")
    return matches[0]


def resolve_model(llm_no: int) -> dict[str, Any]:
    py_home = python_home()
    python_bin = f"/opt/m4-runtime/python/{py_home.name}/bin/python3.12"
    site = "/opt/m4-runtime/ga-env/lib/python3.12/site-packages"
    resolver = (
        "import hashlib,json,pathlib,os;from agentmain import GenericAgent;"
        "a=GenericAgent();n=int(os.environ['M4_LLM_NO']);count=len(a.llmclients);"
        "assert 0<=n<count,f'llm_no {n} out of range';a.next_llm(n);b=a.llmclient.backend;"
        "cfg=pathlib.Path('/opt/genericagent/mykey.py').read_bytes();"
        "print('M4_IDENTITY='+json.dumps({'requested_llm_no':n,'effective_llm_no':a.llm_no,"
        "'model':b.model.lower(),'backend_type':type(b).__name__,'backend_name':b.name,"
        "'available_models':count,'config_sha256':hashlib.sha256(cfg).hexdigest()},sort_keys=True))"
    )
    output = checked([
        "docker", "run", "--rm", "-v", f"{GA_RUNTIME.resolve()}:/opt/m4-runtime:ro",
        "-v", f"{GA_ROOT.resolve()}:/opt/genericagent:ro", "-e", f"M4_LLM_NO={llm_no}",
        "-e", f"PYTHONPATH={site}:/opt/genericagent", "debian:bookworm-slim",
        python_bin, "-c", resolver,
    ], 180)
    marker = next((line for line in output.splitlines() if line.startswith("M4_IDENTITY=")), None)
    if marker is None:
        raise RuntimeError("GA model resolver emitted no identity")
    return json.loads(marker.split("=", 1)[1])


def image_identity() -> dict[str, Any]:
    raw = checked(["docker", "image", "inspect", IMAGE_TAG], 60)
    info = json.loads(raw)[0]
    if info.get("Id") != IMAGE_ID or IMAGE_REF not in (info.get("RepoDigests") or []):
        raise RuntimeError(f"TB2 image mismatch for {IMAGE_TAG}")
    return {"tag": IMAGE_TAG, "image_id": IMAGE_ID, "immutable_ref": IMAGE_REF}


def preflight(llm_no: int = 0) -> dict[str, Any]:
    checked(["docker", "info"], 60)
    if not HARBOR_EXE.exists():
        raise RuntimeError(f"Harbor executable missing: {HARBOR_EXE}")
    ga_hash = tree_hash(GA_ROOT, ga_mode=True)
    expected_ga_hash = os.environ.get("GA_METHOD_EXPECTED_SOURCE_SHA256", "").strip().lower() or GA_SOURCE_SHA256
    if ga_hash != expected_ga_hash:
        raise RuntimeError(f"GA source mismatch: expected {expected_ga_hash}, got {ga_hash}")
    identity = {
        "schema_version": "harbor-tb2-m4-preflight/2",
        "created_at": now(),
        "task_id": f"tb2:{TASK_ID}",
        "terminal_bench": git_identity(TB_ROOT, TB_COMMIT),
        "task_tree_sha256": tree_hash(TASK_ROOT),
        "harbor": {**harbor_identity(),
                   "version": checked([str(HARBOR_EXE), "--version"], 60)},
        "generic_agent": {
            "path": str(GA_ROOT.resolve()),
            "source_sha256": ga_hash,
            "hash_scope": (
                "all runtime files excluding caches, task temp, and mutable "
                "memory/file_access_stats.json telemetry"
            ),
        },
        "runtime": {"root": str(GA_RUNTIME.resolve()), "python_home": python_home().name},
        "image": image_identity(),
        "model": resolve_model(llm_no),
    }
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    (WORK_ROOT / "preflight.json").write_text(json.dumps(identity, indent=2), encoding="utf-8")
    return identity


def collector_ready() -> bool:
    state = run(["docker", "inspect", "-f", "{{.State.Running}}", COLLECTOR_NAME], 30)
    if state.returncode or state.stdout.strip().lower() != "true":
        return False
    try:
        with socket.create_connection(("127.0.0.1", COLLECTOR_PORT), timeout=2):
            return True
    except OSError:
        return False


def collector_output_identity() -> str:
    """Identify the run-scoped host directory mounted at collector /output."""
    normalized = str(OTEL_ROOT.resolve()).replace("\\", "/").casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def collector_matches_output() -> bool:
    inspected = run([
        "docker", "inspect", "--format",
        f'{{{{ index .Config.Labels "{COLLECTOR_OUTPUT_LABEL}" }}}}',
        COLLECTOR_NAME,
    ], 30)
    return (
        inspected.returncode == 0
        and inspected.stdout.strip() == collector_output_identity()
    )


def start_collector() -> None:
    # A collector left by an interrupted prior run may be healthy while still
    # writing into that run's bind-mounted output directory. Never reuse it
    # unless its immutable label identifies this exact OTEL_ROOT.
    if collector_ready() and collector_matches_output():
        return
    existing = run(["docker", "container", "inspect", COLLECTOR_NAME], 30)
    if existing.returncode == 0:
        checked(["docker", "rm", "-f", COLLECTOR_NAME], 60)
    OTEL_ROOT.mkdir(parents=True, exist_ok=True)
    checked([
        "docker", "run", "-d", "--name", COLLECTOR_NAME,
        "--label", f"{COLLECTOR_OUTPUT_LABEL}={collector_output_identity()}",
        "-p", f"127.0.0.1:{COLLECTOR_PORT}:4318",
        "-v", f"{(ROOT / 'config' / 'otel-collector-m2.yaml').resolve()}:/etc/otelcol-contrib/config.yaml:ro",
        "-v", f"{OTEL_ROOT.resolve()}:/output", COLLECTOR_IMAGE,
        "--config=/etc/otelcol-contrib/config.yaml",
    ], 120)
    for _ in range(20):
        if collector_ready():
            return
        time.sleep(1)
    raise RuntimeError("M4 OTel collector did not become ready")


def stop_collector() -> None:
    if run(["docker", "container", "inspect", COLLECTOR_NAME], 30).returncode == 0:
        run(["docker", "stop", "-t", "10", COLLECTOR_NAME], 30)
        run(["docker", "rm", COLLECTOR_NAME], 30)


def harbor_job(
    job_name: str,
    agent: str,
    identity: dict[str, Any] | None = None,
    *,
    agent_timeout_sec: int = 900,
    launcher_timeout_sec: int = 1500,
    agent_timeout_multiplier: float | None = None,
) -> Path:
    if (JOBS_ROOT / job_name).exists():
        raise RuntimeError(f"job already exists: {job_name}")
    command = [
        str(HARBOR_EXE), "jobs", "start", "--job-name", job_name,
        "--jobs-dir", str(JOBS_ROOT.resolve()), "--path", str(TASK_ROOT.resolve()),
        "--agent", agent, "--n-concurrent", "1", "--max-retries", "0", "--yes", "--delete",
    ]
    if agent_timeout_multiplier is not None:
        if agent_timeout_multiplier <= 0:
            raise ValueError("agent_timeout_multiplier must be positive")
        command += ["--agent-timeout-multiplier", str(agent_timeout_multiplier)]
    if identity is not None:
        model = identity["model"]
        mounts = [
            {"type": "bind", "source": str(GA_RUNTIME.resolve()),
             "target": "/opt/m4-runtime", "read_only": True},
            {"type": "bind", "source": str(GA_ROOT.resolve()),
             "target": "/opt/genericagent-source", "read_only": True},
        ]
        command += ["--model", model["model"], "--mounts", json.dumps(mounts)]
        kwargs = {
            "llm_no": model["effective_llm_no"], "run_id": job_name,
            "expected_model": model["model"], "python_home": identity["runtime"]["python_home"],
            "ga_source_sha256": identity["generic_agent"]["source_sha256"],
            "task_id": f"tb2:{TASK_ID}",
            "collector_endpoint": f"http://host.docker.internal:{COLLECTOR_PORT}/v1/traces",
            "timeout_sec": agent_timeout_sec,
        }
        condition = os.environ.get("GA_BASELINE_CONDITION")
        if condition:
            kwargs.update({
                "baseline_condition": condition,
                "experiment_id": os.environ.get("GA_EXPERIMENT_ID", ""),
                "condition_id": os.environ.get("GA_CONDITION_ID", condition),
                "llm_config_name": os.environ.get("GA_LLM_CONFIG_NAME", ""),
                "max_turns": int(os.environ.get("GA_MAX_TURNS", "180")),
            })
        if os.environ.get("GA_M0_MONITOR_ENABLED") == "1":
            kwargs.update({
                "m0_monitor_enabled": True,
                "m0_monitor_config": os.environ["GA_M0_MONITOR_CONFIG"],
                "m0_max_inspections": int(os.environ.get("GA_M0_MAX_INSPECTIONS", "8")),
            })
            if os.environ.get("GA_M1_WORKSPACE_ENABLED") == "1":
                kwargs["m1_workspace_enabled"] = True
            if os.environ.get("GA_M1_ACTIVE_RECONSTRUCTION_ENABLED") == "1":
                kwargs["m1_active_reconstruction_enabled"] = True
        elif os.environ.get("GA_M1_WORKSPACE_ENABLED") == "1":
            raise ValueError("GA_M1_WORKSPACE_ENABLED requires GA_M0_MONITOR_ENABLED")
        ledger_path = os.environ.get("GA_OBLIGATION_LEDGER_CARD_PATH")
        if ledger_path:
            kwargs["obligation_ledger_card_b64"] = base64.b64encode(
                Path(ledger_path).read_bytes()
            ).decode("ascii")
        for key, value in kwargs.items():
            command += ["--ak", f"{key}={value}"]
    result = run(command, launcher_timeout_sec)
    job_dir = JOBS_ROOT / job_name
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "launcher_stdout.log").write_text(result.stdout, encoding="utf-8")
    (job_dir / "launcher_stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Harbor job failed ({result.returncode}): {result.stderr[-4000:]}")
    image_identity()
    return job_dir


def trial_result(job_dir: Path) -> tuple[Path, dict[str, Any]]:
    paths = [p for p in job_dir.glob("*/result.json")]
    if len(paths) != 1:
        raise RuntimeError(f"expected one trial result in {job_dir}, found {len(paths)}")
    return paths[0], json.loads(paths[0].read_text(encoding="utf-8"))


def attr(span: dict[str, Any], key: str) -> str | None:
    for item in span.get("attributes", []):
        if item.get("key") == key:
            return item.get("value", {}).get("stringValue")
    return None


def archive_trace(run_id: str, run_dir: Path) -> dict[str, Any]:
    source = OTEL_ROOT / "traces.jsonl"
    batches, trace_ids, models, count = [], set(), set(), 0
    for line in source.read_text(encoding="utf-8").splitlines() if source.exists() else []:
        if run_id not in line:
            continue
        batch = json.loads(line)
        resources = []
        for resource in batch.get("resourceSpans", []):
            scopes = []
            for scope in resource.get("scopeSpans", []):
                spans = [s for s in scope.get("spans", []) if attr(s, "benchmark.run.id") == run_id]
                if spans:
                    item = {k: v for k, v in scope.items() if k != "spans"}; item["spans"] = spans
                    scopes.append(item); count += len(spans)
                    trace_ids.update(s.get("traceId") for s in spans if s.get("traceId"))
                    models.update(attr(s, "gen_ai.request.model").lower() for s in spans
                                  if attr(s, "gen_ai.request.model"))
            if scopes:
                item = {k: v for k, v in resource.items() if k != "scopeSpans"}; item["scopeSpans"] = scopes
                resources.append(item)
        if resources:
            item = {k: v for k, v in batch.items() if k != "resourceSpans"}; item["resourceSpans"] = resources
            batches.append(item)
    if count == 0 or not trace_ids:
        raise RuntimeError(f"invalid M4 trace identity: spans={count}, trace_ids={sorted(trace_ids)}")
    raw = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in batches)
    trace_path = run_dir / "raw_trace.jsonl"
    trace_path.write_text(raw, encoding="utf-8")
    ordered_trace_ids = sorted(trace_ids)
    return {
        # Backward-compatible only for genuinely single-trace runs. Consumers
        # must use trace_ids for multi-actor Agent/monitor/delegate runs.
        "trace_id": ordered_trace_ids[0] if len(ordered_trace_ids) == 1 else None,
        "trace_ids": ordered_trace_ids,
        "trace_count": len(ordered_trace_ids),
        "span_count": count,
        "observed_models": sorted(models),
        "sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
    }


def finalize_ga(job_name: str, preflight_data: dict[str, Any]) -> dict[str, Any]:
    job_dir = JOBS_ROOT / job_name
    result_path, result = trial_result(job_dir)
    run_dir = RUNS_ROOT / job_name
    run_dir.mkdir(parents=True, exist_ok=False)
    trace = archive_trace(job_name, run_dir)
    expected_model = preflight_data["model"]["model"].lower()
    reward = (result.get("verifier_result") or {}).get("rewards", {}).get("reward")
    metadata = (result.get("agent_result") or {}).get("metadata") or {}
    errors = []
    if result.get("exception_info") is not None: errors.append("Harbor trial has an exception")
    if metadata.get("run_id") != job_name: errors.append("GA run ID is not linked to Harbor job")
    if metadata.get("expected_model") != expected_model: errors.append("agent model metadata mismatch")
    if metadata.get("round_end_seen") is not True: errors.append("GA round-end sentinel was not observed")
    if metadata.get("wrapper_return_code") != 0: errors.append("GA wrapper did not exit successfully")
    if not isinstance(metadata.get("ga_process_return_code"), int):
        errors.append("GA process return code is missing")
    if trace["observed_models"] != [expected_model]: errors.append("OTel observed model mismatch")
    if reward not in (0.0, 1.0): errors.append(f"unexpected verifier reward: {reward}")
    manifest = {
        "schema_version": "harbor-tb2-m4-run/2", "created_at": now(), "run_id": job_name,
        "task_id": f"tb2:{TASK_ID}", "harbor_job_id": result.get("config", {}).get("job_id"),
        "harbor_trial_id": result.get("id"), "harbor_trial_name": result.get("trial_name"),
        "trial_result": str(result_path.resolve()), "reward": reward, "trace": trace,
        "model": preflight_data["model"], "agent_protocol": metadata,
        "source_identity": preflight_data,
        "validation_errors": errors, "valid": not errors,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if errors:
        raise RuntimeError("M4 GA validation failed: " + "; ".join(errors))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "oracle", "controlled-failure", "ga"))
    parser.add_argument("--run-id")
    parser.add_argument("--llm-no", type=int, default=0)
    args = parser.parse_args()
    identity = preflight(args.llm_no)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_id = args.run_id or f"m4-{args.action}-{stamp}"
    if args.action == "preflight":
        print(json.dumps(identity, indent=2)); return
    if args.action == "oracle":
        job = harbor_job(run_id, "oracle")
    elif args.action == "controlled-failure":
        job = harbor_job(run_id, "nop")
    else:
        start_collector()
        try:
            job = harbor_job(run_id, "adapters.harbor_ga_agent:M4GenericAgent", identity)
        finally:
            time.sleep(5)
            stop_collector()
        print(json.dumps(finalize_ga(run_id, identity), indent=2)); return
    _, result = trial_result(job)
    print(json.dumps({"run_id": run_id, "reward": result["verifier_result"]["rewards"]["reward"],
                      "exception": result["exception_info"]}, indent=2))


if __name__ == "__main__":
    main()
