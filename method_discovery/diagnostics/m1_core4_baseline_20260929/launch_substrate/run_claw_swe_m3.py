#!/usr/bin/env python3
"""Build, lock, scan, run, and summarize CLAW-SWE candidates for M3."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CLAW_ROOT = Path(os.environ.get("CLAW_SWE_ROOT", r"E:\LongContext\Ref_Benchmark\CLAW-SWE-Bench"))
GA_HOST = Path(os.environ.get("GA_HOST_ROOT", r"E:\LongContext\GenericAgent-main"))
RUNTIME_ROOT = Path(os.environ.get("M2_RUNTIME_ROOT", r"E:\LongContext\bench_runtime\m2"))
DOCKER_DIR = Path(os.environ.get("DOCKER_CLI_DIR", r"E:\Docker\Desktop\resources\bin"))
DATASET_NAME = "princeton-nlp/SWE-bench_Verified"
DATASET_REVISION = "c104f840cc67f8b6eec6f759ebc8b2693d585d4a"
CLAW_COMMIT = "fcece5f4c0817430ce953b52c80c931a40cd9b83"
GA_SOURCE_SHA256 = "a76afac3cd0bbd0148725f188b8527c83254f4a00310448ac624c81625c1d474"
PARQUET = ROOT / "output" / "m2_claw_swe" / "hf-cache" / "hub" / (
    "datasets--princeton-nlp--SWE-bench_Verified"
) / "snapshots" / DATASET_REVISION / "data" / "test-00000-of-00001.parquet"
REGISTRY = ROOT / "tasks" / "claw_swe_m3_candidates.jsonl"
LOCKS = Path(os.environ.get("CLAW_SWE_M3_LOCKS", ROOT / "tasks" / "claw_swe_m3_locks.jsonl"))
M3_ROOT = Path(os.environ.get("CLAW_SWE_M3_ROOT", ROOT / "output" / "m3_claw_swe"))
READINESS = M3_ROOT / "readiness.jsonl"
SMOKE_RESULTS = ROOT / "tasks" / "claw_swe_m3_smoke_results.jsonl"
SELECTED_RESULTS = ROOT / "tasks" / "claw_swe_m3_selected.jsonl"
BATCH_LEDGER = M3_ROOT / "batch_ledger.jsonl"
INITIAL_REGISTRY = ROOT / "tasks" / "candidates_v1.jsonl"
MINI_50 = CLAW_ROOT / "config" / "verified_mini_50.txt"
M2_SCRIPT = ROOT / "scripts" / "run_claw_swe_m2.py"
EXPANDED_LIMIT = 70
PER_REPOSITORY_LIMIT = 10
COLLECTOR_IMAGE = "otel/opentelemetry-collector-contrib:0.130.1"
COLLECTOR_CONFIG = ROOT / "config" / "otel-collector-m2.yaml"
COLLECTOR_NAME = "m3-otel-collector"
COLLECTOR_PORT = 15318
M2_EVIDENCE_RUN_ID = "m2-repro-ga-sphinx8551-20260719-r1"
M2_ROOT = ROOT / "output" / "m2_claw_swe"

SELECTED_TASKS = (
    "sphinx-doc__sphinx-8551",
    "sphinx-doc__sphinx-8548",
    "sphinx-doc__sphinx-7590",
    "django__django-15629",
    "django__django-11885",
    "django__django-12155",
    "sympy__sympy-13091",
    "sympy__sympy-16597",
    "astropy__astropy-13398",
    "astropy__astropy-13977",
    "pydata__xarray-6992",
    "scikit-learn__scikit-learn-12682",
)
SELECTED_REPOSITORY_QUOTAS = {
    "sphinx-doc/sphinx": 3,
    "django/django": 3,
    "sympy/sympy": 2,
    "astropy/astropy": 2,
    "pydata/xarray": 1,
    "scikit-learn/scikit-learn": 1,
}

OBLIGATION_DRAFTS = {
    "sphinx-doc__sphinx-8551": [
        {
            "id": "implicit-type-local-resolution",
            "requirement": "Unqualified names in implicit :type: and :rtype: fields resolve from the current module and then its parents, consistently with explicit Python-domain cross-references.",
            "outcome_evidence": "official Python-domain cross-reference regression tests",
        },
        {
            "id": "qualified-xref-preservation",
            "requirement": "Fully qualified type names and unrelated Python-domain cross-references retain their existing resolution without new ambiguity warnings.",
            "outcome_evidence": "official regression suite and warning assertions",
        },
    ],
    "sphinx-doc__sphinx-8548": [
        {
            "id": "inherited-data-docstring",
            "requirement": "Autodoc inherited-members resolves an inherited attribute or data-member docstring from the base-class namespace.",
            "outcome_evidence": "official autodoc inherited-members regression tests",
        },
        {
            "id": "docstring-lookup-isolation",
            "requirement": "Normal methods and current-class attributes keep their existing docstring resolution without cross-class cache collisions.",
            "outcome_evidence": "official autodoc suite and focused namespace reproduction",
        },
    ],
    "sphinx-doc__sphinx-7590": [
        {
            "id": "cpp-udl-tokenization",
            "requirement": "C++ numeric literals with user-defined suffixes, including exponent forms such as 6.62607015e-34q_J, parse without an invalid-definition warning.",
            "outcome_evidence": "official parser-domain tests and focused reproduction",
        },
        {
            "id": "cpp-udl-expression-preservation",
            "requirement": "User-defined literals remain valid as operands in compound expressions such as multiplication by 1q_s without weakening existing numeric parsing.",
            "outcome_evidence": "official regression suite and focused expression reproduction",
        },
    ],
    "django__django-11885": [
        {
            "id": "combine-fast-deletes",
            "requirement": "Fast-delete querysets targeting the same model/table are combined into one delete using an OR predicate.",
            "outcome_evidence": "official deletion collector query-count and SQL behavior tests",
        },
        {
            "id": "preserve-delete-boundaries",
            "requirement": "Deletes for different models remain separate and normal parent-object deletion semantics and ordering are preserved.",
            "outcome_evidence": "official cascade and many-to-many regression tests",
        },
    ],
    "django__django-12155": [
        {
            "id": "admindoc-first-line-dedent",
            "requirement": "A view docstring with text on its first line keeps that line and correctly dedents its following lines for admindoc/docutils parsing.",
            "outcome_evidence": "official admindoc docstring regression test",
        },
        {
            "id": "conventional-docstring-preservation",
            "requirement": "Conventional multiline docstrings, including a blank first line, retain valid indentation and default-role directive content.",
            "outcome_evidence": "official documentation utility regression suite",
        },
    ],
    "django__django-15629": [
        {
            "id": "foreign-key-collation-propagation",
            "requirement": "Schema changes propagate an explicitly collated referenced primary key to ForeignKey and OneToOne columns so MySQL can create the constraint.",
            "outcome_evidence": "official schema-editor collation and relation tests",
        },
        {
            "id": "relation-semantics-preservation",
            "requirement": "Nullable and non-nullable relations and targets without explicit collation retain their previous generated SQL and relation semantics.",
            "outcome_evidence": "official migration and schema-editor regression suite",
        },
    ],
    "sympy__sympy-13091": [
        {
            "id": "unknown-type-comparison-delegation",
            "requirement": "Basic equality and inequality with an unknown type return or delegate NotImplemented so the other operand's reflected comparator can run.",
            "outcome_evidence": "official core comparison regression tests with a custom operand",
        },
        {
            "id": "symbolic-comparison-preservation",
            "requirement": "Normal SymPy comparisons remain unchanged, while a comparison unsupported by both operands still has Python's final false equality result.",
            "outcome_evidence": "official SymPy core regression suite",
        },
    ],
    "sympy__sympy-16597": [
        {
            "id": "parity-implies-finite",
            "requirement": "Even, odd, and integer assumptions imply that a Symbol is finite.",
            "outcome_evidence": "official assumptions inference regression tests",
        },
        {
            "id": "assumption-consistency",
            "requirement": "An infinite value cannot also be even or odd, and symbols without a relevant assumption remain unknown rather than being over-inferred.",
            "outcome_evidence": "official assumptions consistency suite",
        },
    ],
    "astropy__astropy-13398": [
        {
            "id": "direct-itrs-observed-transform",
            "requirement": "ITRS to AltAz or HADec uses the direct topocentric transform and does not introduce an erroneous solar-system-barycenter displacement.",
            "outcome_evidence": "official coordinates transformation regression tests",
        },
        {
            "id": "observed-frame-round-trip",
            "requirement": "Inverse transforms, output obstime handling, and AltAz/HADec refraction behavior remain mutually consistent in round trips.",
            "outcome_evidence": "official coordinate round-trip and refraction tests",
        },
    ],
    "astropy__astropy-13977": [
        {
            "id": "duck-array-ufunc-delegation",
            "requirement": "Quantity returns NotImplemented for an unsupported duck-array ufunc operand so its reflected operation can handle compatible units.",
            "outcome_evidence": "official Quantity duck-array regression tests",
        },
        {
            "id": "quantity-unit-errors-preserved",
            "requirement": "Genuinely incompatible units still fail correctly and normal Quantity/ndarray conversions retain their existing behavior.",
            "outcome_evidence": "official units and ufunc regression suite",
        },
    ],
    "pydata__xarray-6992": [
        {
            "id": "data-variables-nonnegative-length",
            "requirement": "DataVariables length and iteration count only coordinate names that still exist in _variables, so length cannot become negative.",
            "outcome_evidence": "official DataVariables representation regression tests",
        },
        {
            "id": "index-reset-state-preservation",
            "requirement": "set_index followed by reset_index(drop=True) yields valid data_vars and repr output without corrupting remaining coordinates or indexes.",
            "outcome_evidence": "official index refactor regression tests",
        },
    ],
    "scikit-learn__scikit-learn-12682": [
        {
            "id": "sparse-coder-max-iter-forwarding",
            "requirement": "SparseCoder exposes max_iter and forwards it to the lasso_cd solver so callers can control convergence iterations.",
            "outcome_evidence": "official decomposition convergence regression tests",
        },
        {
            "id": "sparse-coder-api-preservation",
            "requirement": "The default remains backward compatible, get_params and clone expose the parameter, and other transform algorithms are unaffected.",
            "outcome_evidence": "official estimator API and decomposition regression suite",
        },
    ],
    "sphinx-doc__sphinx-11510": [
        {
            "id": "included-source-read-result",
            "requirement": "Mutations made by a source-read handler to an included reStructuredText file are used in the final doctree and HTML.",
            "outcome_evidence": "official include/source-read test and reproduced HTML content",
        },
        {
            "id": "parent-source-read-result",
            "requirement": "The same source-read substitution continues to apply to the parent document, yielding both expected replacements without duplicate or stale content.",
            "outcome_evidence": "official regression test and final HTML occurrence check",
        },
    ],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PATH"] = str(DOCKER_DIR) + os.pathsep + env.get("PATH", "")
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout, env=env)


def _checked(cmd: list[str], timeout: int = 600) -> str:
    result = _run(cmd, timeout)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def collector_ready() -> bool:
    state = _run(["docker", "inspect", "-f", "{{.State.Running}}", COLLECTOR_NAME], 60)
    if state.returncode != 0 or state.stdout.strip().lower() != "true":
        return False
    try:
        with socket.create_connection(("127.0.0.1", COLLECTOR_PORT), timeout=2):
            return True
    except OSError:
        return False


def ensure_collector() -> None:
    if collector_ready():
        return
    existing = _run(["docker", "container", "inspect", COLLECTOR_NAME], 60)
    if existing.returncode == 0:
        details = json.loads(existing.stdout)[0]
        mounts = {
            mount["Destination"]: Path(mount["Source"]).resolve()
            for mount in details.get("Mounts", [])
        }
        expected = {
            "/etc/otelcol-contrib/config.yaml": COLLECTOR_CONFIG.resolve(),
            "/output": (M3_ROOT / "otel").resolve(),
        }
        port = (
            details.get("HostConfig", {})
            .get("PortBindings", {})
            .get("4318/tcp", [{}])[0]
            .get("HostPort")
        )
        if mounts != expected or port != str(COLLECTOR_PORT):
            removed = _run(["docker", "rm", "-f", COLLECTOR_NAME], 120)
            if removed.returncode:
                raise RuntimeError(
                    "failed to replace mismatched M3 OTel collector: "
                    f"{(removed.stderr or removed.stdout).strip()}"
                )
            existing = subprocess.CompletedProcess([], 1, "", "")
    if existing.returncode == 0:
        started = _run(["docker", "start", COLLECTOR_NAME], 120)
    else:
        (M3_ROOT / "otel").mkdir(parents=True, exist_ok=True)
        started = _run([
            "docker", "run", "-d", "--name", COLLECTOR_NAME,
            "-p", f"127.0.0.1:{COLLECTOR_PORT}:4318",
            "-v", f"{COLLECTOR_CONFIG.resolve()}:/etc/otelcol-contrib/config.yaml:ro",
            "-v", f"{(M3_ROOT / 'otel').resolve()}:/output",
            COLLECTOR_IMAGE, "--config=/etc/otelcol-contrib/config.yaml",
        ], 120)
    if started.returncode:
        raise RuntimeError(f"M3 OTel collector is unavailable: {(started.stderr or started.stdout).strip()}")
    import time

    for _ in range(20):
        if collector_ready():
            return
        time.sleep(1)
    raise RuntimeError("M3 OTel collector did not become ready after restart")


def stop_collector() -> None:
    state = _run(
        ["docker", "inspect", "-f", "{{.State.Running}}", COLLECTOR_NAME],
        60,
    )
    if state.returncode != 0 or state.stdout.strip().lower() != "true":
        return
    stopped = _run(["docker", "stop", COLLECTOR_NAME], 120)
    if stopped.returncode:
        raise RuntimeError(
            "failed to stop M3 OTel collector: "
            f"{(stopped.stderr or stopped.stdout).strip()}"
        )


def canonical_sha256(value: dict[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records), encoding="utf-8")


def _diff_stats(patch: str) -> dict[str, int]:
    import re

    return {
        "changed_files": len(re.findall(r"(?m)^diff --git ", patch)),
        "additions": len(re.findall(r"(?m)^\+(?!\+\+)", patch)),
        "deletions": len(re.findall(r"(?m)^-(?!--)", patch)),
    }


def load_dataset_rows() -> dict[str, dict[str, Any]]:
    if not PARQUET.is_file():
        raise RuntimeError(f"pinned dataset parquet is missing: {PARQUET}")
    import pyarrow.parquet as pq

    return {str(row["instance_id"]): row for row in pq.read_table(PARQUET).to_pylist()}


def initial_ids() -> set[str]:
    return {
        item["source"]["task_id"]
        for item in _jsonl(INITIAL_REGISTRY)
        if item["source"]["benchmark"] == "CLAW-SWE-Bench / SWE-bench Verified"
    }


def build_registry() -> list[dict[str, Any]]:
    rows = load_dataset_rows()
    original = initial_ids()
    missing = sorted(original - rows.keys())
    if missing:
        raise RuntimeError(f"initial candidate IDs missing from pinned dataset: {missing}")
    ranked = []
    for task_id, row in rows.items():
        patch = _diff_stats(str(row.get("patch") or ""))
        tests = _diff_stats(str(row.get("test_patch") or ""))
        problem_chars = len(str(row.get("problem_statement") or ""))
        static_score = (
            patch["changed_files"] * 30
            + min(patch["additions"] + patch["deletions"], 300)
            + min(tests["additions"] + tests["deletions"], 150)
            + min(problem_chars / 100, 30)
        )
        ranked.append({
            "schema_version": "claw-swe-m3-candidate/1",
            "candidate_id": f"swe:{task_id}",
            "instance_id": task_id,
            "repository": row.get("repo"),
            "dataset": DATASET_NAME,
            "dataset_revision": DATASET_REVISION,
            "instance_sha256": canonical_sha256(row),
            "claw_commit": CLAW_COMMIT,
            "in_initial_12": task_id in original,
            "scale_static": {
                "problem_statement_chars": problem_chars,
                "hints_chars": len(str(row.get("hints_text") or "")),
                "gold_patch": patch,
                "test_patch": tests,
                "created_at": row.get("created_at"),
            },
            "selection": {"static_score": round(static_score, 3), "uses_hidden_reference_metrics": True},
            "status": "pending_readiness",
        })
    ranked.sort(key=lambda item: (-item["selection"]["static_score"], item["instance_id"]))
    by_id = {item["instance_id"]: item for item in ranked}
    records = [by_id[task_id] for task_id in sorted(original)]
    repository_counts: dict[str, int] = {}
    for item in records:
        repo = str(item["repository"])
        repository_counts[repo] = repository_counts.get(repo, 0) + 1
    for item in ranked:
        if item["instance_id"] in original:
            continue
        repo = str(item["repository"])
        if repository_counts.get(repo, 0) >= PER_REPOSITORY_LIMIT:
            continue
        records.append(item)
        repository_counts[repo] = repository_counts.get(repo, 0) + 1
        if len(records) == EXPANDED_LIMIT:
            break
    if len(records) != EXPANDED_LIMIT:
        raise RuntimeError(f"could not build {EXPANDED_LIMIT} diverse candidates; got {len(records)}")
    records.sort(key=lambda item: (-item["selection"]["static_score"], item["instance_id"]))
    for rank, item in enumerate(records, 1):
        item["selection"]["static_rank"] = rank
    _write_jsonl(REGISTRY, records)
    return records


def image_tag(instance_id: str) -> str:
    transformed = instance_id.replace("__", "_1776_").lower()
    return f"swebench/sweb.eval.x86_64.{transformed}:latest"


def inspect_image(tag: str) -> dict[str, Any] | None:
    result = _run(["docker", "image", "inspect", tag], 60)
    if result.returncode:
        return None
    info = json.loads(result.stdout)[0]
    repo_digests = sorted(info.get("RepoDigests") or [])
    matching = [item for item in repo_digests if item.split("@", 1)[0] == tag.rsplit(":", 1)[0]]
    if not matching:
        return None
    return {
        "tag": tag,
        "immutable_ref": matching[0],
        "image_id": info.get("Id"),
        "repo_digests": repo_digests,
        "size_bytes": int(info.get("Size") or 0),
    }


def pull_image(tag: str, attempts: int = 3) -> dict[str, Any]:
    errors = []
    for attempt in range(1, attempts + 1):
        result = _run(["docker", "pull", tag], 3600)
        if result.returncode == 0:
            return {"exit_code": 0, "attempts": attempt, "error": None}
        errors.append((result.stderr or result.stdout).strip()[-1000:])
        if attempt < attempts:
            import time

            time.sleep(5 * attempt)
    return {"exit_code": 1, "attempts": attempts, "error": errors[-1] if errors else "unknown pull failure"}


def load_locks() -> dict[str, dict[str, Any]]:
    records = _jsonl(LOCKS)
    by_id: dict[str, dict[str, Any]] = {}
    for item in records:
        task_id = item["instance_id"]
        if task_id in by_id and by_id[task_id] != item:
            raise RuntimeError(f"conflicting immutable locks for {task_id}")
        by_id[task_id] = item
    return by_id


def ensure_lock(candidate: dict[str, Any], image: dict[str, Any]) -> dict[str, Any]:
    locks = load_locks()
    task_id = candidate["instance_id"]
    proposed = {
        "schema_version": "claw-swe-m3-lock/1",
        "instance_id": task_id,
        "claw_commit": CLAW_COMMIT,
        "ga_source_sha256": os.environ.get("GA_METHOD_EXPECTED_SOURCE_SHA256", "").strip().lower() or GA_SOURCE_SHA256,
        "dataset": DATASET_NAME,
        "dataset_revision": DATASET_REVISION,
        "instance_sha256": candidate["instance_sha256"],
        "image": image,
    }
    if task_id in locks:
        if locks[task_id] != proposed:
            raise RuntimeError(f"immutable lock mismatch for {task_id}")
        return locks[task_id]
    records = _jsonl(LOCKS)
    records.append(proposed)
    _write_jsonl(LOCKS, records)
    return proposed


def classify_readiness(checks: dict[str, Any]) -> str:
    if not checks.get("docker_engine"):
        return "env_failure_docker"
    if not checks.get("dataset_identity") or not checks.get("source_identity") or not checks.get("ga_identity"):
        return "harness_identity_failure"
    if not checks.get("image_available"):
        return "env_failure_image_missing"
    if checks.get("deep_requested") and not checks.get("deep_container"):
        return "env_failure_container"
    return "ready"


def _safe_name(instance_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in instance_id)


def deep_check(candidate: dict[str, Any], lock: dict[str, Any]) -> dict[str, Any]:
    task_id = candidate["instance_id"]
    rows = load_dataset_rows()
    row = rows[task_id]
    name = f"m3-ready-{_safe_name(task_id)}"
    runtime_host = RUNTIME_ROOT / "linux"
    python_homes = sorted((runtime_host / "python").glob("cpython-3.12.*-linux-x86_64-gnu"))
    if len(python_homes) != 1:
        raise RuntimeError(f"expected one Python 3.12 runtime, found {len(python_homes)}")
    python_bin = f"/opt/m3-runtime/python/{python_homes[0].name}/bin/python3.12"
    site_packages = "/opt/m3-runtime/ga-env/lib/python3.12/site-packages"
    checks = {"started": False, "base_commit_present": False, "base_commit": False,
              "python": False, "ga_import": False,
              "no_solution_artifacts": False, "cleaned_up": False}
    _run(["docker", "rm", "-f", name], 60)
    cmd = [
        "docker", "run", "-d", "--name", name, "--pids-limit", "512", "--memory", "6g",
        "--memory-swap", "6g", "-v", f"{runtime_host.resolve()}:/opt/m3-runtime:ro",
        "-v", f"{GA_HOST.resolve()}:/opt/genericagent:ro", lock["image"]["immutable_ref"],
        "tail", "-f", "/dev/null",
    ]
    try:
        result = _run(cmd, 180)
        if result.returncode:
            checks["error"] = result.stderr.strip()
            return checks
        checks["started"] = True
        present = _run([
            "docker", "exec", name, "git", "-C", "/testbed", "cat-file", "-e",
            f"{row['base_commit']}^{{commit}}",
        ], 60)
        checks["base_commit_present"] = present.returncode == 0
        reset = _run([
            "docker", "exec", name, "git", "-C", "/testbed", "reset", "--hard", row["base_commit"],
        ], 120)
        clean = _run(["docker", "exec", name, "git", "-C", "/testbed", "clean", "-fd"], 120)
        head = _run(["docker", "exec", name, "git", "-C", "/testbed", "rev-parse", "HEAD"], 60)
        checks["base_commit"] = (
            checks["base_commit_present"] and reset.returncode == 0 and clean.returncode == 0
            and head.returncode == 0 and head.stdout.strip() == row["base_commit"]
        )
        py = _run(["docker", "exec", name, python_bin, "--version"], 60)
        checks["python"] = py.returncode == 0
        code = "import sys;sys.path[:0]=['%s','/opt/genericagent'];import agentmain" % site_packages
        ga = _run(["docker", "exec", name, python_bin, "-c", code], 120)
        checks["ga_import"] = ga.returncode == 0
        scan = _run([
            "docker", "exec", name, "bash", "-lc",
            "find /testbed /root /tmp -type f \\( -iname 'gold.patch' -o -iname 'reference.patch' "
            "-o -iname 'solution.patch' -o -iname 'test.patch' \\) 2>/dev/null",
        ], 120)
        checks["no_solution_artifacts"] = scan.returncode == 0 and not scan.stdout.strip()
    finally:
        _run(["docker", "rm", "-f", name], 120)
        checks["cleaned_up"] = _run(["docker", "container", "inspect", name], 60).returncode != 0
    checks["passed"] = all(checks[key] for key in (
        "started", "base_commit_present", "base_commit", "python", "ga_import",
        "no_solution_artifacts", "cleaned_up"
    ))
    return checks


def validate_source_and_ga() -> tuple[bool, bool]:
    git = ["git", "-c", f"safe.directory={CLAW_ROOT.resolve()}", "-C", str(CLAW_ROOT)]
    head = _checked(git + ["rev-parse", "HEAD"])
    clean = not _checked(git + ["status", "--porcelain", "--untracked-files=all"])
    source_ok = head == CLAW_COMMIT and clean
    spec = importlib.util.spec_from_file_location("m2_for_m3_identity", M2_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    expected_ga_source = os.environ.get("GA_METHOD_EXPECTED_SOURCE_SHA256", "").strip().lower() or GA_SOURCE_SHA256
    ga_ok = module._ga_source_hash() == expected_ga_source
    return source_ok, ga_ok


def scan(scope: str, pull_missing: bool, deep: bool,
         instance_ids: list[str] | None = None) -> list[dict[str, Any]]:
    candidates = _jsonl(REGISTRY) or build_registry()
    if scope == "initial":
        candidates = [item for item in candidates if item["in_initial_12"]]
    if instance_ids:
        requested = set(instance_ids)
        known = {item["instance_id"] for item in candidates}
        unknown = sorted(requested - known)
        if unknown:
            raise RuntimeError(f"readiness requested unknown or out-of-scope IDs: {unknown}")
        candidates = [item for item in candidates if item["instance_id"] in requested]
    engine = _run(["docker", "info"], 60).returncode == 0
    source_ok, ga_ok = validate_source_and_ga()
    rows = load_dataset_rows()
    output = []
    for candidate in candidates:
        task_id = candidate["instance_id"]
        checks: dict[str, Any] = {
            "docker_engine": engine,
            "source_identity": source_ok,
            "ga_identity": ga_ok,
            "dataset_identity": canonical_sha256(rows[task_id]) == candidate["instance_sha256"],
            "deep_requested": deep,
        }
        tag = image_tag(task_id)
        image = inspect_image(tag) if engine else None
        if not image and engine and pull_missing:
            pull = pull_image(tag)
            checks["image_pull_exit_code"] = pull["exit_code"]
            checks["image_pull_attempts"] = pull["attempts"]
            checks["image_pull_error"] = pull["error"]
            image = inspect_image(tag)
        checks["image_available"] = image is not None
        lock = None
        if image and checks["dataset_identity"] and source_ok and ga_ok:
            lock = ensure_lock(candidate, image)
        deep_result = deep_check(candidate, lock) if deep and lock else None
        checks["deep_container"] = bool(deep_result and deep_result.get("passed"))
        record = {
            "schema_version": "claw-swe-m3-readiness/1",
            "scanned_at": _now(),
            "candidate_id": candidate["candidate_id"],
            "instance_id": task_id,
            "repository": candidate["repository"],
            "in_initial_12": candidate["in_initial_12"],
            "static_rank": candidate["selection"]["static_rank"],
            "checks": checks,
            "image": image,
            "deep": deep_result,
        }
        record["status"] = classify_readiness(checks)
        output.append(record)
        print(json.dumps({"instance_id": task_id, "status": record["status"]}, ensure_ascii=False), flush=True)
    _write_jsonl(READINESS, output)
    return output


def configure_m2_for_lock(lock: dict[str, Any]):
    spec = importlib.util.spec_from_file_location("m2_for_m3_run", M2_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    task_id = lock["instance_id"]
    module.INSTANCE_ID = task_id
    module.INSTANCE_SHA256 = lock["instance_sha256"]
    module.IMAGE_TAG = lock["image"]["tag"]
    module.IMAGE_DIGEST = lock["image"]["image_id"]
    module.IMAGE_REF = lock["image"]["immutable_ref"]
    module.WORK_ROOT = M3_ROOT
    module.OTEL_PORT = COLLECTOR_PORT
    row = load_dataset_rows()[task_id]
    module.WORK_ROOT.mkdir(parents=True, exist_ok=True)
    (module.WORK_ROOT / "instance.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    return module


def _otel_string_attribute(span: dict[str, Any], key: str) -> str | None:
    for item in span.get("attributes", []):
        if item.get("key") == key:
            return item.get("value", {}).get("stringValue")
    return None


def archive_run_trace(source: Path, run_id: str, run_dir: Path) -> dict[str, Any]:
    destination = run_dir / "raw_trace.jsonl"
    identity_path = run_dir / "raw_trace_identity.json"
    if destination.exists() or identity_path.exists():
        raise RuntimeError(f"raw trace archive already exists for {run_id}")
    if not source.exists():
        raise RuntimeError(f"shared OTel trace file is missing: {source}")
    filtered_batches = []
    trace_ids: set[str] = set()
    span_count = 0
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or run_id not in line:
            continue
        try:
            batch = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid shared OTLP JSON at line {line_number}: {exc}") from exc
        resources = []
        for resource_spans in batch.get("resourceSpans", []):
            scopes = []
            for scope_spans in resource_spans.get("scopeSpans", []):
                spans = [
                    span for span in scope_spans.get("spans", [])
                    if _otel_string_attribute(span, "benchmark.run.id") == run_id
                ]
                if spans:
                    copied_scope = {key: value for key, value in scope_spans.items() if key != "spans"}
                    copied_scope["spans"] = spans
                    scopes.append(copied_scope)
                    span_count += len(spans)
                    trace_ids.update(span.get("traceId") for span in spans if span.get("traceId"))
            if scopes:
                copied_resource = {key: value for key, value in resource_spans.items() if key != "scopeSpans"}
                copied_resource["scopeSpans"] = scopes
                resources.append(copied_resource)
        if resources:
            copied_batch = {key: value for key, value in batch.items() if key != "resourceSpans"}
            copied_batch["resourceSpans"] = resources
            filtered_batches.append(copied_batch)
    if span_count == 0:
        raise RuntimeError(f"no exported OTel spans found for run {run_id}")
    if len(trace_ids) != 1:
        raise RuntimeError(f"expected one trace ID for {run_id}, got {sorted(trace_ids)}")
    payload = "".join(
        json.dumps(batch, ensure_ascii=False, separators=(",", ":")) + "\n"
        for batch in filtered_batches
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    identity = {
        "schema_version": "claw-swe-m3-raw-trace/1",
        "run_id": run_id,
        "trace_id": next(iter(trace_ids)),
        "span_count": span_count,
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "archived_at": _now(),
    }
    identity_path.write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding="utf-8")
    return identity


def validate_trace_archive(run_dir: Path, run_id: str, expected_trace_id: str) -> tuple[list[str], dict[str, Any]]:
    from observability.validate_trace import validate_trace

    trace_path = run_dir / "raw_trace.jsonl"
    identity_path = run_dir / "raw_trace_identity.json"
    errors = []
    if not trace_path.exists():
        return ["per-run raw trace archive is missing"], {}
    if not identity_path.exists():
        return ["per-run raw trace identity is missing"], {}
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    actual_sha256 = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    if identity.get("run_id") != run_id:
        errors.append("raw trace identity run_id mismatch")
    if identity.get("trace_id") != expected_trace_id:
        errors.append("raw trace identity trace_id mismatch")
    if identity.get("sha256") != actual_sha256:
        errors.append("raw trace archive sha256 mismatch")
    validation_errors, summary = validate_trace(trace_path, expected_trace_id, 1)
    errors.extend(validation_errors)
    if identity.get("span_count") != summary.get("span_count"):
        errors.append("raw trace identity span_count mismatch")
    return errors, summary


def backfill_available_trace_archives() -> list[dict[str, Any]]:
    records = []
    source = M3_ROOT / "otel" / "traces.jsonl"
    for run_dir in sorted((M3_ROOT / "runs").glob("m3-*")):
        if not (run_dir / "immutable_manifest.json").exists() or (run_dir / "raw_trace.jsonl").exists():
            continue
        try:
            identity = archive_run_trace(source, run_dir.name, run_dir)
            records.append({"run_id": run_dir.name, "status": "archived", **identity})
        except RuntimeError as exc:
            records.append({"run_id": run_dir.name, "status": "unavailable", "error": str(exc)})
    return records


def execute(task_id: str, action: str, run_id: str, timeout: int, llm_no: int) -> None:
    lock = load_locks().get(task_id)
    if not lock:
        raise RuntimeError(f"no immutable M3 lock for {task_id}; run readiness first")
    module = configure_m2_for_lock(lock)
    module.require_utf8_mode(sys.flags.utf8_mode)
    if action == "run":
        ensure_collector()
        module.run_agent(run_id, timeout, llm_no)
        archive_run_trace(module.WORK_ROOT / "otel" / "traces.jsonl", run_id,
                          module.WORK_ROOT / "runs" / run_id)
    elif action == "evaluate":
        module.validate_run_manifest(run_id)
        run_dir = module.WORK_ROOT / "runs" / run_id
        payload = {
            "run_id": run_id,
            "manifest_identity_valid": True,
            "manifest_sha256": hashlib.sha256((run_dir / "immutable_manifest.json").read_bytes()).hexdigest(),
            "predictions_sha256": hashlib.sha256((run_dir / "predictions.jsonl").read_bytes()).hexdigest(),
            "dataset_sha256": lock["instance_sha256"],
            "image_digest": lock["image"]["image_id"],
        }
        (run_dir / "evaluation_identity_validation.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (module.WORK_ROOT / "eval" / module.eval_dir_name(run_id)).mkdir(parents=True, exist_ok=True)
        result = subprocess.run(module.build_eval_command(run_id)).returncode
        if result:
            raise RuntimeError(f"official evaluation failed with exit code {result}")
        module.validate_image()
    else:
        raise RuntimeError(f"unsupported execution action: {action}")


def append_batch_event(event: dict[str, Any]) -> None:
    BATCH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with BATCH_LEDGER.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"recorded_at": _now(), **event}, ensure_ascii=False) + "\n")


def batch_run(instance_ids: list[str], batch_id: str, timeout: int, llm_no: int) -> list[dict[str, Any]]:
    known = {item["instance_id"] for item in _jsonl(REGISTRY)}
    if len(instance_ids) != len(set(instance_ids)):
        raise RuntimeError("batch contains duplicate instance IDs")
    unknown = sorted(set(instance_ids) - known)
    if unknown:
        raise RuntimeError(f"batch contains unknown instance IDs: {unknown}")
    records = []
    for task_id in instance_ids:
        run_id = f"m3-{batch_id}-{_safe_name(task_id)}-r1"
        event = {"batch_id": batch_id, "instance_id": task_id, "run_id": run_id}
        run_dir = M3_ROOT / "runs" / run_id
        try:
            if not (run_dir / "predictions.jsonl").exists():
                append_batch_event({**event, "phase": "run", "status": "started"})
                execute(task_id, "run", run_id, timeout, llm_no)
                append_batch_event({**event, "phase": "run", "status": "completed"})
            else:
                append_batch_event({**event, "phase": "run", "status": "resumed_existing_prediction"})
            if _evaluation_for(run_id) is None:
                append_batch_event({**event, "phase": "evaluate", "status": "started"})
                execute(task_id, "evaluate", run_id, timeout, llm_no)
                append_batch_event({**event, "phase": "evaluate", "status": "completed"})
            report = _evaluation_for(run_id)
            record = {**event, "status": "completed", "evaluation": report}
        except Exception as exc:
            record = {**event, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            append_batch_event({**record, "phase": "batch"})
            records.append(record)
            break
        append_batch_event({**record, "phase": "batch"})
        records.append(record)
    return records


def _evaluation_under(root: Path, run_id: str) -> dict[str, Any] | None:
    matches = [
        path for path in root.glob(f"{run_id}*/*.json")
        if path.name.endswith(f".{run_id}.json")
    ]
    if not matches:
        return None
    parsed = [json.loads(path.read_text(encoding="utf-8")) for path in matches]
    outcome_keys = (
        "submitted_instances", "completed_instances", "resolved_instances",
        "unresolved_instances", "empty_patch_instances", "error_instances",
    )
    outcomes = {tuple(int(item.get(key, 0)) for key in outcome_keys) for item in parsed}
    if len(outcomes) != 1:
        raise RuntimeError(f"conflicting official evaluation reports for {run_id}")
    report_path, report = sorted(zip(matches, parsed), key=lambda item: str(item[0]))[-1]
    return {
        "report": str(report_path.relative_to(ROOT)),
        "submitted": int(report.get("submitted_instances", 0)),
        "completed": int(report.get("completed_instances", 0)),
        "resolved": int(report.get("resolved_instances", 0)),
        "unresolved": int(report.get("unresolved_instances", 0)),
        "empty_patch": int(report.get("empty_patch_instances", 0)),
        "errors": int(report.get("error_instances", 0)),
    }


def _evaluation_for(run_id: str) -> dict[str, Any] | None:
    return _evaluation_under(M3_ROOT / "eval", run_id)


def classify_smoke(metadata: dict[str, Any], trace_errors: list[str], evaluation: dict[str, Any] | None) -> str:
    if metadata.get("error") or metadata.get("state") not in {"patch_collected", "completed"}:
        return "env_or_harness_failure"
    if trace_errors:
        return "trace_invalid"
    if not evaluation or evaluation["errors"] or evaluation["completed"] != 1:
        return "verifier_failure"
    return "resolved" if evaluation["resolved"] == 1 else "task_failed"


def summarize_runs() -> list[dict[str, Any]]:
    candidates = {item["instance_id"]: item for item in _jsonl(REGISTRY)}
    results = []
    for run_dir in sorted((M3_ROOT / "runs").glob("m3-ga-*-r*")):
        manifest_path = run_dir / "immutable_manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        task_id = manifest["dataset"]["instance_id"]
        artifact = run_dir / task_id
        metadata_path = artifact / "metadata.json"
        otel_path = artifact / "otel_trace.json"
        if not metadata_path.exists() or not otel_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        otel = json.loads(otel_path.read_text(encoding="utf-8"))
        trace_errors, trace = validate_trace_archive(run_dir, run_dir.name, otel["trace_id"])
        prediction = json.loads((run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()[0])
        patch_stats = _diff_stats(prediction.get("model_patch") or "")
        evaluation = _evaluation_for(run_dir.name)
        status = classify_smoke(metadata, trace_errors, evaluation)
        trajectory_qualified = (
            not trace_errors and trace.get("chat_spans", 0) >= 8
            and trace.get("agent_events", 0) >= 14
        )
        obligations = OBLIGATION_DRAFTS.get(task_id, [])
        results.append({
            "schema_version": "claw-swe-m3-smoke/1",
            "candidate_id": f"swe:{task_id}",
            "instance_id": task_id,
            "repository": candidates.get(task_id, {}).get("repository"),
            "run_id": run_dir.name,
            "status": status,
            "model": manifest["model"],
            "identity": {
                "instance_sha256": manifest["dataset"]["instance_sha256"],
                "image_id": manifest["image"]["image_id"],
                "manifest_validated": (run_dir / "evaluation_identity_validation.json").exists(),
            },
            "agent": metadata["agent"],
            "trace_valid": not trace_errors,
            "trace_errors": trace_errors,
            "trace": trace,
            "patch": patch_stats,
            "evaluation": evaluation,
            "trajectory_qualified": trajectory_qualified,
            "obligation_design": {
                "status": "draft_pending_observation_acquisition_review" if len(obligations) >= 2 else "missing",
                "obligations": obligations,
            },
            "selection_status": (
                "trajectory_candidate_pending_obligations" if trajectory_qualified and len(obligations) >= 2
                else "reject_short_trajectory" if not trajectory_qualified else "pending_obligations"
            ),
        })
    by_task: dict[str, dict[str, Any]] = {}
    for item in results:
        complete = (
            item["trace_valid"] and item["identity"]["manifest_validated"]
            and item["evaluation"] is not None and item["evaluation"]["completed"] == 1
            and item["evaluation"]["errors"] == 0 and item["patch"]["changed_files"] > 0
        )
        rank = (int(complete), item["run_id"])
        current = by_task.get(item["instance_id"])
        if current is None or rank > current["_selection_rank"]:
            by_task[item["instance_id"]] = {**item, "_selection_rank": rank}
    unique_results = []
    for item in sorted(by_task.values(), key=lambda value: value["instance_id"]):
        item.pop("_selection_rank")
        unique_results.append(item)
    _write_jsonl(SMOKE_RESULTS, unique_results)
    return unique_results


def _m2_evidence_record() -> dict[str, Any]:
    run_dir = M2_ROOT / "runs" / M2_EVIDENCE_RUN_ID
    task_id = "sphinx-doc__sphinx-8551"
    artifact = run_dir / task_id
    if not (run_dir / "raw_trace.jsonl").exists():
        archive_run_trace(M2_ROOT / "otel" / "traces.jsonl", M2_EVIDENCE_RUN_ID, run_dir)
    manifest = json.loads((run_dir / "immutable_manifest.json").read_text(encoding="utf-8"))
    metadata = json.loads((artifact / "metadata.json").read_text(encoding="utf-8"))
    otel = json.loads((artifact / "otel_trace.json").read_text(encoding="utf-8"))
    trace_errors, trace = validate_trace_archive(run_dir, M2_EVIDENCE_RUN_ID, otel["trace_id"])
    prediction = json.loads((run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    evaluation = _evaluation_under(M2_ROOT / "eval", M2_EVIDENCE_RUN_ID)
    return {
        "schema_version": "claw-swe-m3-selected/1",
        "candidate_id": f"swe:{task_id}",
        "instance_id": task_id,
        "repository": "sphinx-doc/sphinx",
        "run_id": M2_EVIDENCE_RUN_ID,
        "evidence_milestone": "M2",
        "status": classify_smoke(metadata, trace_errors, evaluation),
        "model": manifest["model"],
        "identity": {
            "instance_sha256": manifest["dataset"]["instance_sha256"],
            "image_id": manifest["image"]["image_id"],
            "manifest_validated": (run_dir / "evaluation_identity_validation.json").exists(),
        },
        "agent": metadata["agent"],
        "trace_valid": not trace_errors,
        "trace_errors": trace_errors,
        "trace": trace,
        "patch": _diff_stats(prediction.get("model_patch") or ""),
        "evaluation": evaluation,
        "trajectory_qualified": not trace_errors and trace.get("chat_spans", 0) >= 8
        and trace.get("agent_events", 0) >= 14,
        "obligation_design": {"status": "specific_draft", "obligations": OBLIGATION_DRAFTS[task_id]},
    }


def finalize_selection() -> list[dict[str, Any]]:
    smoke = {item["instance_id"]: item for item in summarize_runs()}
    smoke["sphinx-doc__sphinx-8551"] = _m2_evidence_record()
    registry = {item["instance_id"]: item for item in _jsonl(REGISTRY)}
    records = []
    for order, task_id in enumerate(SELECTED_TASKS, 1):
        item = smoke.get(task_id)
        if item is None:
            raise RuntimeError(f"selected task has no run evidence: {task_id}")
        evaluation = item.get("evaluation") or {}
        obligations = OBLIGATION_DRAFTS.get(task_id, [])
        evidence_complete = (
            item.get("trace_valid") and item.get("identity", {}).get("manifest_validated")
            and evaluation.get("completed") == 1 and evaluation.get("errors") == 0
            and item.get("patch", {}).get("changed_files", 0) > 0 and len(obligations) >= 2
        )
        if not evidence_complete:
            raise RuntimeError(f"selected task evidence is incomplete: {task_id}")
        repository = item.get("repository") or registry.get(task_id, {}).get("repository")
        records.append({
            **item,
            "schema_version": "claw-swe-m3-selected/1",
            "selection_order": order,
            "repository": repository,
            "evidence_milestone": item.get("evidence_milestone", "M3"),
            "obligation_design": {"status": "specific_draft", "obligations": obligations},
            "selection_status": "accepted_legacy_source_allocation",
            "methodology_status": {
                "grandfathered": True,
                "requires_independent_review": False,
                "ga_result_is_not_selection_evidence": True,
            },
        })
    actual_quotas = {
        repository: sum(item["repository"] == repository for item in records)
        for repository in SELECTED_REPOSITORY_QUOTAS
    }
    if actual_quotas != SELECTED_REPOSITORY_QUOTAS:
        raise RuntimeError(f"selected repository quotas mismatch: {actual_quotas}")
    _write_jsonl(SELECTED_RESULTS, records)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("build-registry")
    sub.add_parser("summarize")
    sub.add_parser("finalize-selection")
    sub.add_parser("archive-available-traces")
    batch_parser = sub.add_parser("batch")
    batch_parser.add_argument("--instance-ids", required=True,
                              help="comma-separated ordered instance IDs")
    batch_parser.add_argument("--batch-id", required=True)
    batch_parser.add_argument("--timeout", type=int, default=3600)
    batch_parser.add_argument("--llm-no", type=int, default=0)
    scan_parser = sub.add_parser("readiness")
    scan_parser.add_argument("--scope", choices=("initial", "all"), default="initial")
    scan_parser.add_argument("--pull-missing", action="store_true")
    scan_parser.add_argument("--deep", action="store_true")
    scan_parser.add_argument("--instance-ids", help="optional comma-separated allowlist")
    for name in ("run", "evaluate"):
        item = sub.add_parser(name)
        item.add_argument("--instance-id", required=True)
        item.add_argument("--run-id", required=True)
        item.add_argument("--timeout", type=int, default=3600)
        item.add_argument("--llm-no", type=int, default=0)
    args = parser.parse_args()
    if args.action == "build-registry":
        records = build_registry()
        print(json.dumps({"candidates": len(records), "initial": sum(i["in_initial_12"] for i in records),
                          "registry": str(REGISTRY)}, indent=2))
    elif args.action == "readiness":
        selected = [item.strip() for item in (args.instance_ids or "").split(",") if item.strip()]
        records = scan(args.scope, args.pull_missing, args.deep, selected or None)
        counts: dict[str, int] = {}
        for item in records:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        print(json.dumps({"total": len(records), "statuses": counts, "output": str(READINESS)}, indent=2))
    elif args.action == "summarize":
        records = summarize_runs()
        print(json.dumps({
            "runs": len(records),
            "statuses": {status: sum(item["status"] == status for item in records)
                         for status in sorted({item["status"] for item in records})},
            "trajectory_qualified": sum(item["trajectory_qualified"] for item in records),
            "output": str(SMOKE_RESULTS),
        }, indent=2))
    elif args.action == "finalize-selection":
        records = finalize_selection()
        print(json.dumps({
            "selected": len(records),
            "resolved": sum(item["evaluation"]["resolved"] for item in records),
            "repositories": {
                repository: sum(item["repository"] == repository for item in records)
                for repository in SELECTED_REPOSITORY_QUOTAS
            },
            "output": str(SELECTED_RESULTS),
        }, indent=2))
    elif args.action == "archive-available-traces":
        records = backfill_available_trace_archives()
        print(json.dumps(records, ensure_ascii=False, indent=2))
    elif args.action == "batch":
        records = batch_run(
            [item.strip() for item in args.instance_ids.split(",") if item.strip()],
            args.batch_id, args.timeout, args.llm_no,
        )
        print(json.dumps(records, ensure_ascii=False, indent=2))
        return 0 if records and all(item["status"] == "completed" for item in records) else 1
    else:
        execute(args.instance_id, args.action, args.run_id, args.timeout, args.llm_no)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
