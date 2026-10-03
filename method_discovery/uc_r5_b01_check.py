"""Zero-model parsing/argument check for the frozen b01 authorizations."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from method_discovery.uc_r5_b01_freeze import (
    BRIDGE, BRIDGE_SOURCE_SHA, CANDIDATE, CHECKLIST_SHA, ORDER, OUT,
    PREREG_SHA, REPO, sha,
)
from method_discovery.uc_r5_execution_entry import bridge_source_hash, load_authorized_slot


def main() -> None:
    manifest = OUT / "RUNNER_MANIFEST.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["secrets_included"] is False
    assert [r["run_id"] for r in payload["runs"]] == [r for _, r in ORDER]
    assert bridge_source_hash() == BRIDGE_SOURCE_SHA
    checks = []
    for condition, run_id in ORDER:
        auth = OUT / f"AUTH_{run_id}.json"
        slot, authorization = load_authorized_slot(run_id, auth)
        assert authorization["runner_manifest_sha256"] == sha(manifest)
        assert authorization["preregistration_sha256"] == PREREG_SHA
        assert authorization["slot_checklist_sha256"] == CHECKLIST_SHA
        assert authorization["candidate_commit"] == CANDIDATE
        assert authorization["bridge_implementation_commit"] == BRIDGE
        assert slot["condition"] == condition
        assert slot["block"] == "b01" and slot["repetition"] == 2
        assert slot["status"] == "not_started"
        env = next(r["environment"] for r in payload["runs"] if r["run_id"] == run_id)
        assert env["GA_BASELINE_CONDITION"] == "original"
        assert env["GA_HOST_ROOT"] == slot["deployment"]["ga_host_root"]
        assert env["BENCHMARK_CAMPAIGN_ROOT"] == slot["output"]["campaign_root"]
        profile = Path(slot["deployment"]["monitor_profile_path"])
        assert sha(profile) == slot["deployment"]["monitor_profile_sha256"]
        config = json.loads(profile.read_text(encoding="utf-8"))["claude_monitor_opus48"]
        assert config["monitor_research_view"] == slot["deployment"]["view"]
        assert config["monitor_research_intent"] == slot["deployment"]["intent"]
        assert config["monitor_research_intent_window_requests"] == 4
        assert config["monitor_dcec"] is True
        assert config["monitor_dcec_working_chars"] == 4000
        # Separate interpreter: the original runner's actual manifest loader
        # expands each assignment without launching a task or a provider.
        probe = '''
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts import run_ultralong_m12_proofs as runner
runner.apply_experiment_manifest(sys.argv[2], sys.argv[3])
print(json.dumps(runner.stage4_agent_kwargs(), sort_keys=True))
'''
        result = subprocess.run(
            [sys.executable, "-c", probe, str(REPO / "long_context_bench"),
             str(manifest), run_id], cwd=REPO, text=True, capture_output=True,
            check=True,
        )
        kwargs = json.loads(result.stdout.strip())
        assert kwargs["baseline_condition"] == "original"
        assert kwargs["monitor_enabled"] is True
        assert kwargs["monitor_config"] == "claude_monitor_opus48"
        assert kwargs["llm_config_name"] == "native_claude_cc_vibe_opus48"
        assert kwargs["max_turns"] == 180
        assert kwargs["experiment_id"] == "" and kwargs["condition_id"] == "original"
        checks.append({"run_id": run_id, "condition_host_only": condition,
                       "authorization_sha256": sha(auth),
                       "private_profile_sha256": sha(profile),
                       "adapter_kwargs": kwargs})
    print(json.dumps({"status": "passed", "manifest_sha256": sha(manifest),
                      "checks": checks, "real_model_requests": 0}, indent=2))


if __name__ == "__main__":
    main()
