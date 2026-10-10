"""Explicit common initialization for a static continuation of C02's root review."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.freeze_run import HOST_PROFILE
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009.freeze_inputs import REPO

sys.path.insert(0, str(REPO / "GenericAgent-main"))
from monitor_agent_core.agent import MonitorAgent  # noqa: E402
from monitor_agent_core.workspace import MonitorWorkspace  # noqa: E402
from monitor_agent_core.runtime import WorkspaceTransitionSampler  # noqa: E402


HANDOFF = {"request_id": "completion-1", "generation": 1, "cursor": 161}
HISTORIC_REVIEW_ID = "34a3f8d394414952bb7b87a3ff67923f"
TASK_TURN = 83
TASK_MAX_TURNS = 300
DIALOGUE_CUTOFF = 418


def candidate_config():
    data = json.loads(HOST_PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    data.update(monitor_adaptive_supervisory_environment=True,
                monitor_contrastive_release_state=True,
                monitor_receding_horizon_release=True,
                monitor_root_epistemic_reestimation=True,
                monitor_live_intervention=True,
                monitor_ase_meta_regulation=False,
                monitor_semantic_continuity=True)
    return data


def prepare_agent(fixture: Path, request: dict, client, agent_type=MonitorAgent):
    workspace = MonitorWorkspace(fixture / "task_evidence", fixture / "monitor_private",
                                 task_mounts={"workspace": fixture / "app"})
    agent = agent_type(client, workspace, max_review_turns=300)
    agent.completion_state = lambda: HANDOFF
    agent.task_budget_state = lambda: (TASK_TURN, TASK_MAX_TURNS)
    agent._seen_completion = copy.deepcopy(HANDOFF)
    agent.completion_pending = True
    agent.frame_kind = "root"
    agent.root_frame_handoff = copy.deepcopy(HANDOFF)
    client.observed_root_handoff = copy.deepcopy(HANDOFF)
    client.recovery_deadline = None
    agent.review_id = HISTORIC_REVIEW_ID
    agent._ase_initialization_complete = True
    agent._ase_reference_ready_reported = True
    client.review_id = HISTORIC_REVIEW_ID
    agent.dcm.review_id = HISTORIC_REVIEW_ID
    agent.dcm.model_turn = 3
    agent.dcm.tool_sequence = 10
    agent.control_echo.review_id = HISTORIC_REVIEW_ID
    agent.situation.review_id = HISTORIC_REVIEW_ID
    agent.situation.shown_cursor = HANDOFF["cursor"]
    agent.situation.shown_this_review = True
    agent.situation.committed_cursor = HANDOFF["cursor"]
    files, errors = WorkspaceTransitionSampler._scan(fixture / "app")
    if errors:
        raise RuntimeError(f"Workspace scan unavailable: {errors}")
    agent.situation.scan = files
    client.restore_history(request["messages"][:-1])
    client.system = request["system"]
    return agent


def certify_cutoff(fixture: Path, source_dialogue: Path):
    actual = (fixture / "monitor_private/audit/dialogue.jsonl").read_bytes()
    source_prefix = b"".join(source_dialogue.read_bytes().splitlines(keepends=True)[:DIALOGUE_CUTOFF])
    lines = actual.splitlines()
    if len(lines) != DIALOGUE_CUTOFF:
        raise RuntimeError("Historical dialogue prefix length drifted")
    if actual != source_prefix:
        raise RuntimeError("Historical dialogue prefix bytes drifted")
    events = [json.loads(line) for line in lines]
    if events[-1].get("event") != "tool_result" or events[-1].get("review_id") != HISTORIC_REVIEW_ID:
        raise RuntimeError("C02 boundary is not after the historical tool receipt")
    forbidden = {"crs_proposed", "crs_confirmed", "rhr_entered", "rhr_final_release_confirmed",
                 "rer_transition_requested", "rer_frame_entered", "rer_frame_restarted"}
    if any(row.get("event") in forbidden for row in events):
        raise RuntimeError("Unrecovered active CRS/RHR/RER state is possible at cutoff")
    if sum(row.get("event") == "curator_echo_delivery_confirmed" for row in events) != sum(
            row.get("event") == "curator_echo_consumed" for row in events):
        raise RuntimeError("Unrecovered active Control Echo is possible at cutoff")
    return {"dialogue_prefix_lines": len(lines),
            "dialogue_prefix_sha256": hashlib.sha256(actual).hexdigest(),
            "historical_review_id": HISTORIC_REVIEW_ID,
            "root_handoff": HANDOFF, "task_turn": TASK_TURN,
            "historic_review_model_turns": 3, "historic_review_tool_calls": 10,
            "active_crs": False, "active_rhr": False, "active_rer": False,
            "active_control_echo": False}
