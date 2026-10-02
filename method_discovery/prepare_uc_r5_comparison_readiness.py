"""Zero-model UC-R5 comparison readiness inventory and private L1 bundles.

This tool deliberately has no scientific run or provider entry point.  It
creates secret-bearing deployment copies outside Git and publishes only an
allowlisted, non-secret identity projection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


FROZEN = "232281d650d062bdc6a6030f40ccb904c1ac0851"
BASE = "6c72477fce3350c82baf74a9ca8a96c87742be5b"
PROFILE = "claude_monitor_opus48"
TASK_PROFILE = "native_claude_cc_vibe_opus48"
CONDITIONS = {"C0": ("off", "off"), "RP": ("flat", "note"),
              "AP": ("framed", "note"), "RB": ("flat", "routed"),
              "AB": ("framed", "routed")}
ORDER = [
    ("ktx-0.13.0-roadmap", 2, ["RP", "C0", "RB", "AB", "AP"]),
    ("ktx-0.13.0-roadmap", 1, ["RB", "RP", "AB", "C0", "AP"]),
    ("ktx-0.13.0-roadmap", 3, ["RP", "C0", "RB", "AP", "AB"]),
    ("fyn-2.2.0-roadmap", 1, ["AB", "RB", "RP", "AP", "C0"]),
    ("fyn-2.2.0-roadmap", 2, ["RP", "RB", "AB", "C0", "AP"]),
    ("fyn-2.2.0-roadmap", 3, ["C0", "RB", "AP", "AB", "RP"]),
]
PUBLIC_MODEL_FIELDS = ("provider", "model", "api_mode", "max_tokens", "context_win",
                       "max_retries", "read_timeout", "timeout", "temperature",
                       "thinking_type", "reasoning_effort", "transport_route",
                       "monitor_dcec", "monitor_dcec_working_chars",
                       "monitor_research_view", "monitor_research_intent",
                       "monitor_research_intent_window_requests")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2,
                                sort_keys=True).encode("utf-8") + b"\n")


def tree_identity(root: Path) -> dict:
    digest = hashlib.sha256()
    count = 0
    for item in sorted(root.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"symlink in task asset: {item}")
        if not item.is_file() or ".git" in item.relative_to(root).parts:
            continue
        relative = item.relative_to(root).as_posix().encode()
        data = item.read_bytes()
        digest.update(relative + b"\0" + data)
        count += 1
    return {"sha256": digest.hexdigest(), "file_count": count}


def file_identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path), "sha256": sha(data), "bytes": len(data)}


def public_config(config: dict) -> dict:
    return {key: config[key] for key in PUBLIC_MODEL_FIELDS if key in config}


def slots() -> list[dict]:
    result = []
    for block, (task, repetition, sequence) in enumerate(ORDER, 1):
        for position, condition in enumerate(sequence, 1):
            opaque = secrets.token_hex(12)
            result.append({"block": f"b{block:02d}", "position": position,
                           "task": f"roadmapbench:{task}", "repetition": repetition,
                           "condition": condition, "run_id": opaque,
                           "live_root": f"E:\\runs\\{opaque}", "status": "not_started"})
    assert len(result) == 30 and len({row["run_id"] for row in result}) == 30
    assert all(not Path(row["live_root"]).exists() for row in result)
    return result


def prepare(repo: Path, historical: Path, private: Path, output: Path) -> dict:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    if head != FROZEN:
        raise RuntimeError(f"expected frozen candidate {FROZEN}, got {head}")
    if private.exists() or output.exists():
        raise FileExistsError("private and output roots must both be unused")
    original_source = historical / "GenericAgent-main"
    original_monitor = historical / "monitor_config" / "models.local.json"
    original_task_config = original_source / "mykey.py"
    for path in (original_monitor, original_task_config):
        if not path.is_file():
            raise FileNotFoundError(path)

    sys.path.insert(0, str(repo / "GenericAgent-main"))
    from monitor_agent_core.configuration import load_profile
    sys.path.insert(0, str(repo / "long_context_bench"))
    from adapters.isolated_setup import ENVIRONMENT_NOTE
    from scripts.isolated_run_bundle import build_bundle

    base_profile = load_profile(PROFILE, original_monitor)
    task_profile = runpy.run_path(str(original_task_config))[TASK_PROFILE]
    proposal_file = historical / "long_context_bench" / "tasks" / "ultralong_m12_roadmapbench_proposal.jsonl"
    proposals = {row["source_task_id"]: row for row in
                 (json.loads(line) for line in proposal_file.read_text(encoding="utf-8").splitlines()
                  if line.strip())}
    private.mkdir(parents=True)
    output.mkdir(parents=True)
    staged = private / "staged_source"
    shutil.copytree(repo / "GenericAgent-main", staged,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.local.json"))
    shutil.copy2(original_task_config, staged / "mykey.py")
    bundles = {}
    profile_proofs = {}
    for condition, (view, intent) in CONDITIONS.items():
        config = dict(base_profile, monitor_dcec=True, monitor_dcec_working_chars=4000,
                      monitor_research_view=view, monitor_research_intent=intent,
                      monitor_research_intent_window_requests=4)
        config_path = private / f"profile_{condition}.json"
        write_json(config_path, {PROFILE: config})
        loaded = load_profile(PROFILE, config_path)
        assert loaded == config
        bundle_source, _ = build_bundle(private / f"bundle_{condition}", staged,
                                        historical / "bench_runtime" / "m2" / "linux",
                                        "cpython-3.12.12-linux-x86_64-gnu", TASK_PROFILE,
                                        PROFILE, 15340, monitor_profile_path=config_path)
        deployed = json.loads((bundle_source / "monitor_agent_core" /
                               "models.local.json").read_text(encoding="utf-8"))[PROFILE]
        assert deployed["monitor_research_view"] == view
        assert deployed["monitor_research_intent"] == intent
        assert deployed["monitor_research_intent_window_requests"] == 4
        assert deployed["monitor_dcec"] is True
        proof = {"source": public_config(loaded), "bundled": public_config(deployed),
                 "source_profile_sha256": sha(config_path.read_bytes()),
                 "bundle_snapshot_sha256": tree_identity(bundle_source)["sha256"],
                 "deployed_profile_sha256": sha((bundle_source / "monitor_agent_core" /
                                                 "models.local.json").read_bytes()),
                 "worker": None, "observed_model": None}
        profile_proofs[condition] = proof
        bundles[condition] = str(bundle_source)
    common = {key: {k: v for k, v in profile_proofs[key]["source"].items()
                    if k not in {"monitor_research_view", "monitor_research_intent"}}
              for key in CONDITIONS}
    assert len({canonical(value) for value in common.values()}) == 1
    assert len({canonical({k: v for k, v in profile_proofs[key]["bundled"].items()
                           if k not in {"monitor_research_view", "monitor_research_intent"}})
                for key in CONDITIONS}) == 1
    write_json(output / "CONFIG_PROPAGATION.json", {
        "profile_name": PROFILE, "task_profile_name": TASK_PROFILE,
        "task_profile": public_config(task_profile),
        "task_profile_sha256": sha(canonical(task_profile)),
        "source_code_tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD:GenericAgent-main"], cwd=repo, text=True).strip(),
        "profile_variants": profile_proofs,
        "L1": "passed", "L2_container_worker": "blocked_docker_unavailable",
        "observed_model_identity": None, "private_bundle_roots": bundles,
        "secrets_in_report": False})

    assets = {"proposal": file_identity(proposal_file), "tasks": {}}
    for task in ("ktx-0.13.0-roadmap", "fyn-2.2.0-roadmap"):
        root = historical / "long_context_bench" / ".cache" / "m12_roadmap_tasks" / task
        if not root.is_dir() or task not in proposals:
            raise FileNotFoundError(f"task cache/proposal missing: {task}")
        row = proposals[task]
        instruction = (root / "instruction.md").read_bytes()
        actual = instruction + ENVIRONMENT_NOTE.encode("utf-8")
        task_dir = output / "public_task_inputs" / task
        task_dir.mkdir(parents=True)
        (task_dir / "original_instruction.txt").write_bytes(instruction)
        (task_dir / "actual_task_input.txt").write_bytes(actual)
        (task_dir / "monitor_original_task.txt").write_bytes(actual)
        assets["tasks"][task] = {
            "cache_root": str(root), "task_tree": tree_identity(root),
            "proposal_row_sha256": sha(canonical(row)),
            "source_revision": row.get("source_revision"),
            "image_proposal": row.get("proposal", {}).get("image"),
            "image_tag": row.get("docker_image"),
            "actual_image_id": None, "repo_digest": None,
            "image_inspection": "blocked_docker_unavailable",
            "instruction": file_identity(root / "instruction.md"),
            "task_toml": file_identity(root / "task.toml"),
            "dockerfile": file_identity(root / "environment" / "Dockerfile"),
            "public_repo": tree_identity(root / "environment" / "repo"),
            "hidden_tests_identity_only": tree_identity(root / "tests"),
            "solution_identity_only": tree_identity(root / "solution"),
            "actual_task_input_sha256": sha(actual),
            "monitor_original_task_sha256": sha(actual),
            "input_transform": "UTF-8 instruction bytes followed by frozen ENVIRONMENT_NOTE bytes",
            "environment_note_sha256": sha(ENVIRONMENT_NOTE.encode("utf-8")),
            "image_contents_inspected": False,
        }
    write_json(output / "TASK_ASSETS.json", assets)

    schedule = slots()
    write_json(output / "SLOT_DRAFT.json", {"slots": schedule, "execution_authorized": False})
    prereg = {
        "kind": "UC-R5-CMP-READY-v1-draft", "execution_authorized": False,
        "candidate_commit": FROZEN, "production_baseline": BASE,
        "allocation_order": [row["condition"] for row in schedule],
        "slot_file": "SLOT_DRAFT.json", "conditions": CONDITIONS,
        "tasks": list(assets["tasks"]), "task_max_turns": 180,
        "max_agent_seconds": 10000, "monitor_intent_window": 4,
        "L1": "passed", "L2": "blocked_docker_unavailable",
        "actual_image_identity_verified": False,
        "observed_model_identity": None, "worker_provider_ready_identity": None,
        "isolation_image_scan": None, "native_verifier_binding": None,
        "comparison_approved": None, "scientific_record_count": 0,
        "no_record_level_rerun": True,
    }
    write_json(output / "PREREGISTRATION_DRAFT.json", prereg)
    return {"tasks": len(assets["tasks"]), "conditions": len(CONDITIONS),
            "slots": len(schedule), "L1": "passed", "L2": "blocked_docker_unavailable"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.repo, args.historical, args.private, args.output),
                     sort_keys=True))
