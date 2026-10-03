"""One-time zero-model materialization of the four path-control trial inputs."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid

from method_discovery import uc_r5_execution_entry as inherited
from method_discovery.uc_r5_execution_bridge import file_sha
from method_discovery.uc_path_control_entry import PLAN_ROOT, MANIFEST, PLAN, REPO


OLD = REPO / "method_discovery/runs/uc_r5_comparison_v1_20261003/SLOT_EXECUTION_CHECKLIST.json"
READINESS = REPO / "method_discovery/runs/uc_r5_cmp_readiness_20261003/ENVIRONMENT_DRAFT.json"
PRIVATE = Path(r"E:\uc_path_control_private_20261003")
CAMPAIGN = Path(r"E:\LongContext\long_context_bench\output\uc_path_control_v0_20261003")
SOURCES = (
    "monitor_agent_core/agent.py", "monitor_agent_core/working_context.py",
    "monitor_agent_core/path_control_v0.py", "tests/test_path_control_v0.py",
)
ORDER = (("fyn-2.2.0-roadmap", "BASE"), ("fyn-2.2.0-roadmap", "PATH"),
         ("ktx-0.13.0-roadmap", "PATH"), ("ktx-0.13.0-roadmap", "BASE"))
CANDIDATE = "7911aefd770788d78041e324c4033a16e607fba4"


def write_once(path, obj):
    if path.exists():
        raise RuntimeError(f"Frozen artifact exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())


def prepare_private(condition, build_bundle, digest_tree, m4):
    launch = PRIVATE / f"launch_{condition}"
    source = launch / "GenericAgent-main"
    profile = launch / "monitor_config/models.local.json"
    if not source.is_dir() or not profile.is_file():
        raise RuntimeError("Frozen private C0-derived launch material is missing")
    for relative in SOURCES:
        destination = source / relative
        shutil.copy2(REPO / "GenericAgent-main" / relative, destination)
    profiles = json.loads(profile.read_text(encoding="utf-8"))
    config = profiles["claude_monitor_opus48"]
    if (config.get("monitor_research_view", "off") != "off"
            or config.get("monitor_research_intent", "off") != "off"
            or config.get("monitor_dcec") is not True):
        raise RuntimeError("Inherited Monitor profile is not frozen C0")
    config["monitor_path_control_v0"] = condition == "PATH"
    profile.write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")
    bundle = PRIVATE / f"bundle_{condition}"
    if bundle.exists():
        raise RuntimeError("Private bundle destination already exists")
    copied, _ = build_bundle(
        bundle, source, m4.GA_RUNTIME, m4.python_home().name,
        "native_claude_cc_vibe_opus48", "claude_monitor_opus48", 15340,
        monitor_profile_path=profile)
    deployed = copied / "monitor_agent_core/models.local.json"
    return {
        "ga_host_root": str(source), "monitor_profile_path": str(profile),
        "monitor_profile_sha256": file_sha(profile),
        "bundle_source": str(copied), "bundle_snapshot_sha256": digest_tree(copied),
        "bundle_deployed_profile_sha256": file_sha(deployed),
        "ga_source_tree_hash_runner_scope": m4.tree_hash(source, ga_mode=True),
        "configured_monitor_model": config["model"],
        "monitor_path_control_v0": condition == "PATH",
        "view": "off", "intent": "off", "intent_window": 4,
    }


def main():
    if PLAN.exists() or MANIFEST.exists():
        raise RuntimeError("Path-control plan already frozen")
    bench = Path(r"E:\LongContext\long_context_bench")
    sys.path.insert(0, str(bench))
    from scripts.isolated_run_bundle import build_bundle, digest_tree
    from scripts import run_harbor_tb2_m4 as m4

    original = json.loads(OLD.read_text(encoding="utf-8"))["proposed_slots"]
    common = json.loads(READINESS.read_text(encoding="utf-8"))["common"]
    deployments = {name: prepare_private(name, build_bundle, digest_tree, m4)
                   for name in ("BASE", "PATH")}
    if deployments["BASE"]["ga_source_tree_hash_runner_scope"] != deployments["PATH"]["ga_source_tree_hash_runner_scope"]:
        raise RuntimeError("BASE and PATH deployed code trees differ")

    slots, runs = [], []
    for position, (task_id, condition) in enumerate(ORDER, 1):
        template = next(row for row in original if row["runner"]["task_id"] == task_id)
        slot = copy.deepcopy(template)
        run_id = uuid.uuid4().hex[:24]
        live_root = Path(r"E:\runs") / run_id
        if live_root.exists() or (CAMPAIGN / "jobs" / run_id).exists() or (CAMPAIGN / "runs" / run_id).exists():
            raise RuntimeError("Generated run identity already used")
        slot.update({"block": "path-control-v0", "position": position,
                     "ordinal": position, "condition": condition,
                     "candidate_commit": CANDIDATE, "run_id": run_id,
                     "live_root": str(live_root), "status": "not_started"})
        slot["deployment"] = copy.deepcopy(deployments[condition])
        slot["output"] = {"campaign_root": str(CAMPAIGN),
                          "jobs_subdir": f"jobs/{run_id}", "runs_subdir": f"runs/{run_id}"}
        slot["runner"]["run_id_argument"] = run_id
        slots.append(slot)
        env = dict(common)
        env.update({"GA_BASELINE_CONDITION": "original",
                    "GA_HOST_ROOT": slot["deployment"]["ga_host_root"],
                    "BENCHMARK_CAMPAIGN_ROOT": str(CAMPAIGN),
                    "GA_METHOD_EXPECTED_SOURCE_SHA256": slot["deployment"]["ga_source_tree_hash_runner_scope"],
                    "GA_EXPERIMENT_HARNESS_SHA256": slot["runner"]["execution_harness_sha256"]})
        runs.append({"run_id": run_id, "environment": env})

    sys.path.insert(0, str(REPO / "GenericAgent-main"))
    from monitor_agent_core.path_control_v0 import (
        SYSTEM_PROMPT, CONTINUATION_PROMPT, WORKING_GUIDANCE, WINDOW_GUIDANCE,
        WINDOW_LIMIT,
    )
    text_hashes = {key: hashlib.sha256(value.encode()).hexdigest() for key, value in {
        "system": SYSTEM_PROMPT, "continuation": CONTINUATION_PROMPT,
        "working": WORKING_GUIDANCE, "window_guidance": WINDOW_GUIDANCE,
    }.items()}
    plan = {"schema": "path-control-v0-four-trial-plan/1",
            "execution_authorized": False, "candidate_commit": CANDIDATE,
            "parent_commit": "914db59abdf7f4341d0c16503efbbea5fe5b5085",
            "run_order": [slot["run_id"] for slot in slots],
            "task_condition_order": list(ORDER), "slots": slots,
            "text_sha256": text_hashes, "window_limit_characters": WINDOW_LIMIT,
            "window_rule": "Current complete root event or latest complete event; latest distinct complete event with nonempty tool_results; complete lines only; calls and returns before text; fixed two-event split; 2400-character total cap.",
            "real_model_calls_before_freeze": 0}
    write_once(PLAN, plan)
    write_once(MANIFEST, {"secrets_included": False, "runs": runs})
    for slot in slots:
        write_once(PLAN_ROOT / f"AUTH_{slot['run_id']}.json", {
            "execution_authorized": True, "run_id": slot["run_id"],
            "candidate_commit": CANDIDATE, "plan_sha256": file_sha(PLAN),
            "runner_manifest": str(MANIFEST.resolve()),
            "runner_manifest_sha256": file_sha(MANIFEST),
            "bridge_source_sha256": inherited.bridge_source_hash(),
            "task_model": "claude-opus-4-8"})
    print(json.dumps({"plan_sha256": file_sha(PLAN), "run_order": plan["run_order"],
                      "ga_code_hash": deployments["BASE"]["ga_source_tree_hash_runner_scope"]}, indent=2))


if __name__ == "__main__":
    main()
