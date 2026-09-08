"""Prepare a manual-supervision manifest; never start a task or call a model."""
import argparse
import json
from pathlib import Path

from clean_monitor_prepare_real_task_gate import build_manifest


def prepare(output, suffix):
    manifest = build_manifest("roadmapbench:fyn-2.2.0-roadmap", suffix, output)
    run = manifest["runs"][0]
    run["condition"] = "manual-monitor"
    run["task_role"] = "phase1_human_observation_diagnostic"
    env = run["environment"]
    for key in list(env):
        if key.startswith("GA_MONITOR_"):
            del env[key]
    env.update({
        "GA_EXPERIMENT_ID": "phase1-manual-monitor",
        "GA_CONDITION_ID": "manual-monitor",
        "GA_LLM_CONFIG_NAME": "native_claude_cc_vibe_opus48",
        "GA_MANUAL_COMPLETION_ENABLED": "1",
        "GA_MANUAL_COMPLETION_TIMEOUT_SECONDS": "600",
    })
    manifest["candidate"] = "human-supervision-diagnostic-not-method-candidate"
    manifest["supervisor"] = "current interactive assistant; no automatic monitor model"
    manifest["limitations"] = [
        "Supervisor knows prior Fyne failures; not blind or causal effect evidence",
        "No hidden verifier feedback during execution",
        "Interruption receipt is not proof of uptake; inspect subsequent public actions",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(output), "run_id": run["run_id"],
                      "status": "prepared_not_executed"}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suffix", default="phase1-manual-20260907-r1")
    args = parser.parse_args()
    prepare(args.output, args.suffix)
