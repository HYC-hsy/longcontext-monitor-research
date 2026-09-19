"""Prepare one immutable dual-Opus root-checkpoint capture run; never execute it."""

from __future__ import annotations

import json
from pathlib import Path

from clean_monitor_prepare_real_task_gate import build_manifest


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "method_discovery" / "runs" / "dual_opus_20260919"
CONTRACT = ROOT / "GenericAgent-main" / "monitor_agent_core" / "dual_opus_contract.json"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "dual_opus_root_capture_r2_manifest.json"
    if path.exists():
        raise SystemExit("Manifest exists; do not overwrite an experiment identity")
    manifest = build_manifest(
        "roadmapbench:fyn-2.2.0-roadmap",
        "dual-opus48-root-capture-20260919-r2",
        path,
    )
    manifest["candidate"] = "frozen-supervisor-real-state-capture"
    manifest["model_contract"] = json.loads(CONTRACT.read_text(encoding="utf-8"))
    manifest["frozen_method"] = {
        "parent": "b64ef43 plus connection-layer acceptance repairs",
        "memory": "persistent provider history and frozen monitor private state",
        "compression": "existing MonitorProviderClient semantic compaction",
        "concurrency": "existing wake-owned control and concurrent follow-up",
        "capture_target": "first valid root handoff",
        "independent_c_online": False,
    }
    env = manifest["runs"][0]["environment"]
    env.update({
        "GA_LLM_CONFIG_NAME": "native_claude_cc_vibe_opus48",
        "GA_MONITOR_CONFIG": "claude_monitor_opus48",
        "GA_MONITOR_EXPECTED_MODEL": "claude-opus-4-8",
        "GA_MODEL_CONTRACT_FILE": "monitor_agent_core/dual_opus_contract.json",
        "GA_MONITOR_ROOT_CAPTURE_REQUIRED": "1",
        "GA_PMA_ENABLED": "0",
        "GA_MONITOR_GROUNDED_CONTEXT": "0",
        "GA_MONITOR_HANDOFF_VALIDATION": "0",
        "GA_MONITOR_ADVICE_REVISION": "0",
        "GA_MONITOR_FEEDBACK_FOCUS": "0",
        "GA_MONITOR_INQUIRY": "0",
        "GA_MONITOR_TOOL_FEEDBACK": "0",
        "GA_MONITOR_ACTIVE_WORKING_CONTEXT": "0",
        "GA_MONITOR_LIVE_AWARENESS": "0",
        "GA_MONITOR_DECISION_CONTEXT": "0",
        "GA_MONITOR_INDEPENDENT_C": "0",
        "GA_MONITOR_PMA_MEMORY": "0",
        "GA_MONITOR_ROOT_DECISION_CONTRACT": "0",
        "GA_MONITOR_ROOT_SIMPLE_CHECK": "0",
        "GA_MONITOR_TASK_MODEL": "0",
        "GA_MONITOR_HYBRID_CONTROL": "0",
    })
    manifest["comparison_limits"] = (
        "Capture-only normal Supervisor run. No online C and no method claim. "
        "The first valid root handoff is selected before any diagnostic result.")
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
