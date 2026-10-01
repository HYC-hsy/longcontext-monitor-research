"""One-record research launcher; online source is the frozen 6c72477 archive."""

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
RESEARCH_ROOT = Path(r"E:\LongContext")
SOURCE = Path(r"E:\longcontext-dynamic-observer-transition-e521")
REFERENCE = RESEARCH_ROOT / "method_discovery/runs/dynamic_observer_v0c_adoption_20261001/r2"
REFERENCE_BUNDLE = (RESEARCH_ROOT / "long_context_bench/output/dynamic_observer_v0c_adoption_20261001"
                    / "isolated_bundles/dynamic-observer-v0c-adoption-20261001-02/source")
OLD = "e52107808527cb42ad2169db721b69b450a674fc"
CANDIDATE = "6c72477fce3350c82baf74a9ca8a96c87742be5b"
RUN = "dynamic-observer-wtv-kitex-transfer-20261002-01"
TASK = "ktx-0.13.0-roadmap"
TURNS = 300
SECONDS = 7200
EXPECTED_DIFF = ["monitor_agent_core/runtime.py"]

prior = RESEARCH_ROOT / "method_discovery/diagnostics/ader_v2c_real_dev_pilot_20261001/launch_ader_v2c.py"
spec = importlib.util.spec_from_file_location("archived_roadmap_launcher", prior)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def frozen_source(destination):
    head = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(SOURCE), "status", "--porcelain",
                                     "--untracked-files=no"], text=True)
    if head != CANDIDATE or dirty:
        raise RuntimeError("frozen production worktree identity mismatch")
    changed = subprocess.check_output(["git", "-C", str(SOURCE), "diff", "--name-only",
                                       OLD, CANDIDATE, "--", "GenericAgent-main"], text=True).splitlines()
    if sorted(changed) != sorted(["GenericAgent-main/monitor_agent_core/runtime.py",
                                  "GenericAgent-main/tests/test_workspace_transition_view.py"]):
        raise RuntimeError("unreviewed production source delta: " + repr(changed))
    archive = subprocess.check_output(["git", "-C", str(SOURCE), "archive", "--format=zip",
                                       CANDIDATE, "GenericAgent-main"])
    destination.mkdir(parents=True, exist_ok=False)
    with base.zipfile.ZipFile(base.io.BytesIO(archive)) as stream:
        stream.extractall(destination)
    ga = destination / "GenericAgent-main"
    (ga / "temp").mkdir(exist_ok=True)
    key = base.RUNNER_ROOT / "GenericAgent-main/mykey.py"
    profile = base.RUNNER_ROOT / "monitor_config/models.local.json"
    if base.sha(key.read_bytes()) != base.TASK_PROFILE_SHA:
        raise RuntimeError("Task private profile changed")
    if base.sha(profile.read_bytes()) != base.MONITOR_PROFILE_SHA:
        raise RuntimeError("Supervisor private profile changed")
    base.shutil.copyfile(key, ga / "mykey.py")
    (destination / "monitor_config").mkdir()
    base.shutil.copyfile(profile, destination / "monitor_config/models.local.json")
    tree = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse",
                                    CANDIDATE + "^{tree}"], text=True).strip()
    return ga, {
        "commit": head, "source_tree": tree, "git_archive_sha256": base.sha(archive),
        "task_profile_sha256": base.sha(key.read_bytes()),
        "monitor_profile_sha256": base.sha(profile.read_bytes()),
        "production_diff_from_v0c": EXPECTED_DIFF,
    }


def configure_runner(ga, output):
    base.configure_runner(ga, output)
    base.runner.COLLECTOR_NAME = "dynamic-observer-wtv-kitex-transfer-otel"


def identity_gate(output):
    gate_root = output / "identity_gate" / RUN
    ga, identity = frozen_source(gate_root / "source_input")
    base.common_environment(TURNS)
    configure_runner(ga, gate_root)
    preflight = base.runner.preflight("roadmapbench", 0, TASK)
    manifest = json.loads((REFERENCE / "proof/manifest.json").read_text(encoding="utf-8"))
    old = manifest["source_identity"]
    prior_source = json.loads((REFERENCE / "source_identity/source_identity.json").read_text(encoding="utf-8"))
    prior_isolation = json.loads((REFERENCE / "source_identity/isolation_identity.json").read_text(encoding="utf-8"))
    trial = json.loads((REFERENCE / "trial/config.json").read_text(encoding="utf-8"))
    comparisons = {key: [preflight[key], old[key]] for key in
                   ("task_id", "task_tree_sha256", "source_revision", "image", "harbor",
                    "runtime", "model", "adapter")}
    mismatches = [key for key, pair in comparisons.items() if pair[0] != pair[1]]
    for key in ("task_profile_sha256", "monitor_profile_sha256"):
        if identity[key] != prior_source[key]:
            mismatches.append(key)
    if prior_source["commit"] != OLD:
        mismatches.append("reference_source_commit")
    if manifest["integration_budget_sec"] != SECONDS or manifest["online_checker_feedback"]:
        mismatches.append("budget_or_online_feedback")
    if manifest["completion_evaluation"] != "native_deterministic_verifier":
        mismatches.append("verifier_lifecycle")
    kwargs = trial["agent"]["kwargs"]
    expected = {"max_turns": TURNS, "timeout_sec": SECONDS,
                "llm_config_name": "native_claude_cc_vibe_opus48",
                "monitor_enabled": True, "monitor_config": "claude_monitor_opus48",
                "baseline_condition": "original", "condition_id": "original"}
    mismatches.extend("archived_agent_kwargs." + k for k, v in expected.items() if kwargs.get(k) != v)
    if trial["agent_timeout_multiplier"] != SECONDS / 7200:
        mismatches.append("agent_timeout_multiplier")
    if trial["environment"]["type"] != "docker" or trial["agent"]["model_name"] != "claude-opus-4-8":
        mismatches.append("environment_or_model")
    if not REFERENCE_BUNDLE.is_dir():
        raise RuntimeError("reference isolated bundle unavailable")
    copied, compose = base.build_bundle(
        gate_root / "bundle", ga, base.runner.m4.GA_RUNTIME,
        preflight["runtime"]["python_home"], "native_claude_cc_vibe_opus48",
        "claude_monitor_opus48", base.runner.COLLECTOR_PORT,
        monitor_profile_path=ga.parent / "monitor_config/models.local.json")
    isolation = json.loads((compose.parent / "isolation_identity.json").read_text(encoding="utf-8"))
    for key in ("profile", "model_names", "secrets_in_evidence", "task_network_mode",
                "gateway_transport_sha256"):
        if isolation[key] != prior_isolation[key]:
            mismatches.append("isolation." + key)
    before, after = base.file_hashes(REFERENCE_BUNDLE), base.file_hashes(copied)
    actual_diff = sorted(path for path in before.keys() | after.keys() if before.get(path) != after.get(path))
    if actual_diff != EXPECTED_DIFF:
        mismatches.append("isolated_source_diff")
    report = {
        "run_id": RUN, "reference_run_id": manifest["run_id"],
        "status": "PASS" if not mismatches else "FAIL", "source_identity": identity,
        "comparison": {k: {"current": a, "reference": b, "match": a == b}
                       for k, (a, b) in comparisons.items()},
        "isolation": {k: isolation[k] for k in ("profile", "snapshot_sha256", "model_names",
                                                "secrets_in_evidence", "task_network_mode",
                                                "gateway_transport_sha256")},
        "reference_isolation_snapshot_sha256": prior_isolation["snapshot_sha256"],
        "isolated_source_diff": actual_diff, "mismatches": mismatches,
        "task_max_turns": TURNS, "integration_budget_seconds": SECONDS,
        "model_requests": 0,
    }
    path = HERE / "IDENTITY_GATE.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--gate-only", action="store_true")
    action.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    registration = json.loads((HERE / "PREREGISTRATION.json").read_text(encoding="utf-8"))
    if (registration["run_id"] != RUN or registration["treatment_commit"] != CANDIDATE
            or registration["task"] != "roadmapbench:" + TASK
            or registration["task_max_turns"] != TURNS
            or registration["integration_budget_seconds"] != SECONDS):
        raise RuntimeError("launcher differs from preregistration")
    output = Path(args.output_root).resolve()
    if args.gate_only:
        report = identity_gate(output)
        print(json.dumps({"run_id": RUN, "gate": report["status"],
                          "mismatches": report["mismatches"]}, indent=2))
        if report["status"] != "PASS":
            raise RuntimeError("zero-model identity gate failed")
        return
    if any((output / name / RUN).exists() for name in ("jobs", "runs", "isolated_bundles", "source_inputs")):
        raise RuntimeError("record already started: no record-level rerun")
    gate = json.loads((HERE / "IDENTITY_GATE.json").read_text(encoding="utf-8"))
    if gate["status"] != "PASS" or gate["run_id"] != RUN or gate["mismatches"]:
        raise RuntimeError("zero-model identity gate is not passed")
    ga, identity = frozen_source(output / "source_inputs" / RUN)
    if identity != gate["source_identity"]:
        raise RuntimeError("execution source differs from gate")
    (output / "source_inputs" / RUN / "source_identity.json").write_text(
        json.dumps(identity, indent=2), encoding="utf-8")
    base.common_environment(TURNS)
    configure_runner(ga, output)
    result = base.runner.run_proof("roadmapbench", RUN, 0, SECONDS, TASK)
    (output / "source_inputs" / RUN / "result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
